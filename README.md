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

    # Deploy drupal application
    juju deploy drupal --channel beta
 
    # Deploy PostgreSQL
    juju deploy --num-units 3 postgresql-k8s postgresql
 
    # Add database relation
    juju add-relation drupal:db postgresql:db

Once the deployment settles and all units are in `active` / `idle` state, point 
your browser to the IP address of the `drupal` unit.

The operator generates admin's password if it is not explicitly configured. Retrieve 
the generated password by running juju `get-admin-password` action as follows:

    juju run-action drupal/0 get-admin-password --wait

You can now log in, as an `admin` user, with a password provided in the juju action
result.

### Access logs from Drupal container

You can access logs from Drupal container (including Pebble logs and Apache logs) 
by running `kubectl logs` command, e.g.:

    kubectl logs <drupal-pod-name> \
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
 
    # Deploy drupal
    juju deploy ./drupal.charm --resource drupal-image=drupal

    # Or refresh already deployed charm
    juju refresh drupal --path=./drupal.charm

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests

## Further work

- Implement a relation to nginx-ingress-integrator (with `service-hostname` by default
set to `self.app.name`)

- PostgreSQL is a sane default for a database. Optional support for MySQL driver 
could be added in the future,

- Implement support for High Availability. Make it possible to deploy multiple `drupal`
units. Figure out the way for sharing storage between `drupal` units, i.e. `sites`, 
`modules`, `profiles` and `themes` directories.

- Make it possible to attach already existing `sites`, `modules`, `profiles` 
or `themes` volumes,

- Provide an easy access for Drush CLI -- an industry standard tool for interacting
with and managing Drupal sites. This could be implemented as juju actions. 
Alternatively, drush could be accessed after ssh'ing to the `drupal` unit.

- Consider deploying Drush in a separate container, instead of installing it inside
the Drupal container,

- Add tests.
