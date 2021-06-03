# Drupal Operator

## Description

Charmed Drupal Operator deploys Drupal content management system (CMS) into 
a Kubernetes model. 

> [...] It's used to make many of the websites and applications you use every day. 
Drupal has great standard features, like easy content authoring, reliable 
performance, and excellent security. But what sets it apart is its flexibility; 
modularity is one of its core principles. Its tools help you build the versatile, 
structured content that dynamic web experiences need.
>
> -- <cite>https://www.drupal.org/about<cite/>

This charmed operator deploys the Docker official Drupal image, maintained by the 
Docker community (https://hub.docker.com/_/drupal).

The operator also installs Drush CLI into the Drupal container. Drush is then used
for automating the installation of the Drupal site. 

## Usage

This operator requires relation with PostgreSQL database. Run the following 
commands to deploy a simple model.

    # Deploy drupal-k8s
    juju deploy cs:~phausman/drupal-k8s drupal

    # Customize installation options (see more config options in config.yaml)
    juju config drupal site-name="Hello, Drupal Operator!"
    juju config drupal site-mail="hello@drupal-k8s.juju"
 
    # Deploy PostgreSQL
    juju deploy --num-units 3 cs:~postgresql-charmers/postgresql-k8s postgresql
 
    # Add database relation
    juju add-relation drupal:db postgresql:db

Once the deployment settles and all units are in `active` / `idle` state, point 
your browser to the IP address of the drupal-k8s unit.

The operator generates admin's password if it is not explicitly configured. Retrieve 
the generated password by running juju `get-admin-password` action as follows:

    juju run-action drupal/0 get-admin-password --wait

You can now log in, as an `admin` user, with a password provided in the juju action
result.

### Access logs from Drupal container

You can access logs from Drupal container (including Pebble logs and Apache logs) 
by running `kubectl logs` command, e.g.:

    kubectl logs <drupal-k8s-pod-name> \
      --container drupal --namespace <juju-model-name> --follow 

## Developing

Source code for this charm is hosted on GitHub: 
https://github.com/phausman/charm-drupal-k8s

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

Build and deploy a local version of the charm:

    # Build the charm
    charmcraft build
 
    # Deploy drupal-k8s
    juju deploy ./drupal-k8s.charm --resource drupal-image=drupal drupal

    # Or refresh already deployed charm
    juju refresh drupal --path=./drupal-k8s.charm

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests

## Further work

- Add support for MySQL and SQLite databases,

- Implement High Availability, share `sites`, `modules`, `profiles` and `themes`
volumes between `drupal-k8s` units,

- Make it possible to attach already existing `sites`, `modules`, `profiles` 
or `themes` volumes,

- Provide an easy access for Drush CLI -- an industry standard tool for interacting
with and managing Drupal sites,

- Consider deploying Drush in a separate container, instead of installing it inside
the Drupal container,

- Add tests.
