#!/bin/bash

export PATH="$PATH:$HOME/.composer/vendor/bin"

cd /var/www/html/sites

echo "Installing Drupal with 'drush site-install ...'"

drush site-install standard \
  --yes --verbose --debug \
  --account-mail="${ACCOUNT_MAIL}" \
  --account-name="${ACCOUNT_NAME}" \
  --account-pass="${ACCOUNT_PASS}" \
  --site-name="${SITE_NAME}" \
  --site-mail="${SITE_MAIL}" \
  --db-url="pgsql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

chown -R www-data:www-data /var/www/html/sites

echo "Finished installing Drupal"
