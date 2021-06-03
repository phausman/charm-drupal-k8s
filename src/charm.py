#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.

"""Drupal Operator Charm"""

import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

import ops.lib

pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")

logger = logging.getLogger(__name__)

DATABASE_NAME = "drupal"


class DrupalOperatorCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        # Initialize persistent variables
        self._stored.set_default(
            db_conn_str=None,
            db_uri=None,
            db_ro_uris=[],
            drupal_installed=False,
            account_password=self._get_admin_password(),
        )

        # Lifecycle events
        self.framework.observe(self.on.drupal_pebble_ready, self._on_drupal_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

        # Actions
        self.framework.observe(self.on.get_admin_password_action, self._on_get_admin_password)

        # PostgreSQL
        self.db = pgsql.PostgreSQLClient(self, "db")  # 'db' relation in metadata.yaml

        self.framework.observe(
            self.db.on.database_relation_joined, self._on_database_relation_joined
        )
        self.framework.observe(self.db.on.master_changed, self._on_master_changed)
        self.framework.observe(self.db.on.standby_changed, self._on_standby_changed)
        self.framework.observe(
            self.db.on.database_relation_broken, self._on_database_relation_broken
        )

    def _on_drupal_pebble_ready(self, event):
        """Define and start a workload using the Pebble API."""

        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload

        # Push the install_drush.sh script to workload container
        src_path = "src/install_drush.sh"
        dst_path = "/charm/bin/install_drush.sh"
        with open(src_path, "r", encoding="utf-8") as f:
            container.push(dst_path, f, permissions=0o755)

        # Push the install_drupal.sh script to workload container
        src_path = "src/install_drupal.sh"
        dst_path = "/charm/bin/install_drupal.sh"
        with open(src_path, "r", encoding="utf-8") as f:
            container.push(dst_path, f, permissions=0o755)

        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "drupal layer",
            "description": "pebble config layer for drupal",
            "services": {
                "drupal": {
                    "override": "replace",
                    "summary": "Runs apache2 in a foreground",
                    "command": "docker-php-entrypoint apache2-foreground",
                    "startup": "disabled",
                    "before": ["install-drush"],
                },
                "install-drush": {
                    "override": "replace",
                    "summary": "Installs Drush to workload container",
                    "command": "/charm/bin/install_drush.sh",
                    "startup": "enabled",
                },
            },
        }
        # Add intial Pebble config layer using the Pebble API
        container.add_layer("drupal", pebble_layer, combine=True)

        # Autostart any services that were defined with startup: enabled
        container.autostart()

    def _on_config_changed(self, _):
        """Handle changed configuration.

        This method implements operator's state machine. Initial implementation is
        driven by two flags: `drupal_installed` and `db_conn_str`.

        `drupal_installed` is boolean flag. It's value denotes whether Drupal has
        already been installed or not. Drupal installation is implemented with a
        `drush site-install ...` command, run inside the workload container.

        `db_conn_str` is a string holding the connection string to the PostgreSQL
        database backing Drupal installation. Once the relation with `postgresql-k8s`
        charm is created, this variable is populated with a database connection string.
        As soon as the database connection string is available, Drupal installation can
        begin.
        """
        container = self.unit.get_container("drupal")

        if self._stored.drupal_installed:
            if self._stored.db_conn_str:
                # Drupal is already installed and database relation is present.
                # This is a normal operation. `drupal` service should be started, if
                # it is not running already.
                logger.info(
                    "Drupal is installed, database is ready. All good."
                    "Starting `drupal` service and setting Active state."
                )

                # Start `drupal` service if it is not running already
                if not container.get_service("drupal").is_running():
                    logger.info("`drupal` service is not running, starting...")
                    container.start("drupal")

                # Set Active status
                self.unit.status = ActiveStatus()
            else:
                # Drupal is already installed but the database is not ready. Most likely
                # the database relation has been broken. Drupal cannot operate without
                # a backing database, so we need to stop `drupal` service and set
                # Blocked status
                logger.info("Drupal is installed but the database is not ready.")

                # Stop `drupal` service if it is still running
                if container.get_service("drupal").is_running():
                    logger.info("`drupal` service is running, stopping...")
                    container.stop("drupal")

                # Set Blocked status
                self.unit.status = BlockedStatus("Waiting for relation with the database")
        else:
            if self._stored.db_conn_str:
                # Drupal is not installed yet but the database is ready. Therefore we
                # are now ready to install Drupal.
                logger.info(
                    "Drupal is not installed, database is ready. Starting Drupal installation."
                )

                # Parse db_conn_str and pull database configuration elements
                # Example db_conn_str:
                #   dbname=drupal fallback_application_name=drupal host=10.152.183.143
                #   password=XdngqkWJSNMX5brHPsjB3MB9wZd4FzBw4xLBXc8s port=5432 user=drupal
                db_config = {}
                for db_config_item in self._stored.db_conn_str.split():
                    key = db_config_item.split("=")[0]
                    value = db_config_item.split("=")[1]
                    db_config[key] = value

                # Define an updated Pebble layer configuration,
                # including a new, `install-drupal` service
                pebble_layer = {
                    "summary": "drupal layer",
                    "description": "pebble config layer for drupal",
                    "services": {
                        "drupal": {
                            "override": "replace",
                            "summary": "drupal",
                            "command": "docker-php-entrypoint apache2-foreground",
                            "startup": "disabled",
                            "before": ["install-drupal"],
                        },
                        "install-drush": {
                            "override": "replace",
                            "summary": "Installs Drush to workload container",
                            "command": "/charm/bin/install_drush.sh",
                            "startup": "enabled",
                        },
                        "install-drupal": {
                            "override": "replace",
                            "summary": "install drupal",
                            "command": "/charm/bin/install_drupal.sh",
                            "startup": "disabled",
                            "environment": {
                                "ACCOUNT_MAIL": self.config["account-mail"],
                                "ACCOUNT_NAME": self.config["account-name"],
                                "ACCOUNT_PASS": self._stored.account_password,
                                "SITE_NAME": self.config["site-name"],
                                "SITE_MAIL": self.config["site-mail"],
                                "DB_USER": db_config["user"],
                                "DB_PASS": db_config["password"],
                                "DB_HOST": db_config["host"],
                                "DB_PORT": db_config["port"],
                                "DB_NAME": db_config["dbname"],
                            },
                        },
                    },
                }

                # Update layer configuration
                container.add_layer("drupal", pebble_layer, combine=True)

                # Start `install-drupal` service
                if not container.get_service("install-drupal").is_running():
                    self.unit.status = MaintenanceStatus("Installing Drupal...")

                    # Start `install-drupal` service and wait for it to finish
                    pebble = container.pebble
                    wait_on = pebble.start_services(["install-drupal"])
                    pebble.wait_change(wait_on)

                    # Set `drupal_installed` flag
                    self._stored.drupal_installed = True

                    # Now that Drupal is installed, start `drupal` service
                    # and set Active status.
                    container.start("drupal")
                    self.unit.status = ActiveStatus()

                else:
                    # `install-drupal` service has just been added and it should not
                    # be running yet. If we end up here, it means that something is
                    # totally wrong.
                    logger.error(
                        "`install-drupal` service is running, this is not expected."
                        "Setting Blocked state."
                    )
                    self.unit.status = BlockedStatus(
                        "`install-drupal` service is running, this is not expected"
                    )

            else:
                # Drupal is not yet installed and the database relation has not been
                # created yet. Therefore we cannot proceed with Drupal installation.
                # Set Blocked state and wait for database relation.
                logger.info(
                    "Drupal is not installed, database is not ready. "
                    "Waiting for the database relation."
                )

                self.unit.status = BlockedStatus("Waiting for relation with the database")

    #
    # Actions
    #

    def _on_get_admin_password(self, event):
        """Get admin password"""
        event.set_results({"password": self._stored.account_password})

    #
    # PostgreSQL relation handlers
    #

    def _on_database_relation_joined(self, event: pgsql.DatabaseRelationJoinedEvent):
        if self.model.unit.is_leader():
            # Provide requirements to the PostgreSQL server.
            event.database = DATABASE_NAME  # Request database named DATABASE_NAME
            event.extensions = [
                "citext:public"
            ]  # Request the citext extension installed (public schema)
        elif event.database != DATABASE_NAME:
            # Leader has not yet set requirements. Defer, incase this unit
            # becomes leader and needs to perform that operation.
            event.defer()
            return

    def _on_master_changed(self, event: pgsql.MasterChangedEvent):
        if event.database != DATABASE_NAME:
            # Leader has not yet set requirements. Wait until next event,
            # or risk connecting to an incorrect database.
            return

        # The connection to the primary database has been created,
        # changed or removed. More specific events are available, but
        # most charms will find it easier to just handle the Changed
        # events. event.master is None if the master database is not
        # available, or a pgsql.ConnectionString instance.
        self._stored.db_conn_str = None if event.master is None else event.master.conn_str
        self._stored.db_uri = None if event.master is None else event.master.uri

        logger.debug("db_uri: %s", self._stored.db_uri)
        logger.debug("db_conn_str: %s", self._stored.db_conn_str)

        # Emit config_changed event so that the charm can configure Drupal with a DB
        self.on.config_changed.emit()

    def _on_standby_changed(self, event: pgsql.StandbyChangedEvent):
        if event.database != DATABASE_NAME:
            # Leader has not yet set requirements. Wait until next event,
            # or risk connecting to an incorrect database.
            return

        # Charms needing access to the hot standby databases can get
        # their connection details here. Applications can scale out
        # horizontally if they can make use of the read only hot
        # standby replica databases, rather than only use the single
        # master. event.stanbys will be an empty list if no hot standby
        # databases are available.
        self._stored.db_ro_uris = [c.uri for c in event.standbys]

    def _on_database_relation_broken(self, event):
        # Clear database-related configuration
        self._stored.db_conn_str = None
        self._stored.db_uri = None
        self._stored.db_ro_uris = []

        # Emit config-changed event, so that the charm can stop `drupal` service
        self.on.config_changed.emit()

    #
    # Custom methods
    #

    def _get_admin_password(self):
        """Get site admin password

        Return password defined in the charm `account-password` option. If
        `account-password` option is not configured, generate a safe password.
        Generated password can be later retrieved with the juju action
        `get-admin-password`.
        """
        config_account_password = self.config.get("account-password")
        if config_account_password:
            # Use password defined in charm configuration
            return config_account_password
        else:
            # Otherwise generate a safe password (https://stackoverflow.com/a/39596292)
            import secrets
            import string

            alphabet = string.ascii_letters + string.digits
            account_password = "".join(secrets.choice(alphabet) for i in range(16))

            return account_password


if __name__ == "__main__":
    main(DrupalOperatorCharm)
