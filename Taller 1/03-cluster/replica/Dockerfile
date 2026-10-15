FROM postgres:16
COPY replica-entrypoint.sh /usr/local/bin/replica-entrypoint.sh
RUN chmod +x /usr/local/bin/replica-entrypoint.sh
ENTRYPOINT ["replica-entrypoint.sh"]
