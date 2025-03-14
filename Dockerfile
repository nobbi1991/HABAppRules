FROM python:3.13 AS buildimage

COPY . /tmp/app_install

RUN set -eux; \
# wheel all packages for habapp
	cd /tmp/app_install; \
	pip wheel --wheel-dir=/root/wheels .

FROM python:3.13

COPY --from=buildimage /root/wheels /root/wheels
COPY container/entrypoint.sh /entrypoint.sh

ENV HABAPP_HOME=/habapp \
	USER_ID=9001 \
	GROUP_ID=9001 \
	TZ=Europe/Berlin

RUN set -eux; \
# Install required dependencies
	apt-get update; \
	DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
		gosu \
		tini; \
	ln -s -f $(which gosu) /usr/local/bin/gosu; \
	apt-get clean; \
	rm -rf /var/lib/apt/lists/*; \
	mkdir -p ${HABAPP_HOME}; \
	mkdir -p ${HABAPP_HOME}/config; \
# install habapp_rules
	pip3 install \
    	--no-index \
    	--find-links=/root/wheels \
		habapp_rules; \
# prepare entrypoint script
	chmod +x /entrypoint.sh; \
# clean up
	rm -rf /root/wheels

WORKDIR ${HABAPP_HOME}
VOLUME ["${HABAPP_HOME}/config"]
ENTRYPOINT ["/entrypoint.sh"]

CMD ["gosu", "habapp", "tini", "--", "python", "-m", "HABApp", "--config", "./config"]
