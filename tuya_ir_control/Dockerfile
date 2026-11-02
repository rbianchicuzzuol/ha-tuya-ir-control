ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BUILD_VERSION

# The Home Assistant base-python image uses its own Python version.
# Installing aiohttp with that interpreter avoids Alpine py3-* packages
# being installed for a different Python ABI.
RUN python3 -m pip install --no-cache-dir "aiohttp>=3.11,<4" "aiomqtt==2.5.1"

COPY rootfs /
RUN chmod a+x /etc/services.d/tuya-ir/run

LABEL io.hass.type="app" \
      io.hass.version="$BUILD_VERSION" \
      io.hass.arch="$BUILD_ARCH"
