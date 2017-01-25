#!/bin/bash

./cli.sh -username admin -password xldeploy -f `pwd`/importEnvironments-11.py -- -e `pwd`/envtest.csv -x "{'password':'admin!'}"


