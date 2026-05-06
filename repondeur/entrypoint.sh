#!/bin/sh
# Substitue les variables d'environnement dans les configs Asterisk puis démarre.
set -eu

SRC=/etc/asterisk-templates
DST=/etc/asterisk

mkdir -p "$DST"

for tpl in "$SRC"/*.conf; do
  fname=$(basename "$tpl")
  echo "[entrypoint] Rendu de $fname"
  envsubst < "$tpl" > "$DST/$fname"
done

# S'assurer que les répertoires runtime existent et sont accessibles
mkdir -p /var/run/asterisk /var/spool/asterisk/voicemail /var/log/asterisk
chown -R asterisk:asterisk /var/run/asterisk /var/spool/asterisk /var/log/asterisk /etc/asterisk

exec "$@"
