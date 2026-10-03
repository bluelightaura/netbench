#!/bin/sh
# Поднять sshd и отдать управление штатному запуску FRR.
set -eu
/usr/sbin/sshd
exec /sbin/tini -- /usr/lib/frr/docker-start
