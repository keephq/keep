#!/bin/bash
set -e

echo "include_dir = '/etc/postgresql/conf.d'" >> "$PGDATA/postgresql.conf"
