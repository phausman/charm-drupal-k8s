#!/bin/bash

echo "Installing Drush with Composer..."
composer global require drush/drush:8.*
composer global update
echo "Finished installing Drush"

# psql is needed by drush. We need to install postgresql-client.
echo "Installing postgresql-client..."
apt update --yes
apt install --yes postgresql-client
echo "Finished installing postgresql-client"
