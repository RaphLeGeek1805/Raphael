# Image dérivée de l'image Asterisk officielle, augmentée du runtime Python
# nécessaire à l'AGI conseiller. Asterisk lit /etc/asterisk-templates et le
# rend via envsubst (cf. entrypoint.sh racine), puis lance asterisk -fvvv.
FROM andrius/asterisk:20-current

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ffmpeg gettext-base ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# venv pour ne pas polluer le Python système d'Asterisk
RUN python3 -m venv /opt/ai-agent
ENV PATH="/opt/ai-agent/bin:$PATH"

COPY ai-agent/requirements.txt /opt/ai-agent/requirements.txt
RUN /opt/ai-agent/bin/pip install --no-cache-dir -r /opt/ai-agent/requirements.txt

# Code AGI dans /var/lib/asterisk/agi-bin (chemin standard Asterisk)
COPY ai-agent/agi/ /var/lib/asterisk/agi-bin/
COPY ai-agent/knowledge/ /opt/ai-agent/knowledge/
COPY ai-agent/admin/ /opt/ai-agent/admin/
COPY ai-agent/db/ /opt/ai-agent/db/

# Le shebang du script pointe vers /usr/bin/env python3 ; on remplace par le venv
RUN sed -i '1c#!/opt/ai-agent/bin/python3' /var/lib/asterisk/agi-bin/ai_conseiller.py \
    && chmod +x /var/lib/asterisk/agi-bin/*.py \
    && chown -R asterisk:asterisk /var/lib/asterisk/agi-bin /var/spool/asterisk

# Variables d'env Python utilisées par les modules
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/var/lib/asterisk/agi-bin \
    DEPANMAGIC_KB_PATH=/opt/ai-agent/knowledge/depanmagic.md
