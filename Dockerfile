# Contour Studio — single-image deployment (spec section 9).
#
# Base: Chainguard Wolfi. It's a minimal, security-hardened distro that ships
# almost no OS packages (no perl, no shell cruft), so image scanners
# (Grype/Trivy) report near-zero vulnerabilities. It's glibc-based, so the
# standard Python math wheels (numpy/scipy/shapely/contourpy) install normally
# with no source builds. Rebuild periodically to stay patched — the GitHub
# Actions workflow does this weekly.
FROM cgr.dev/chainguard/wolfi-base:latest

# python 3.12 + pip, and cairo (the native library behind cairosvg for PNG
# export). --no-cache keeps the apk index out of the final image.
RUN apk add --no-cache python-3.12 py3.12-pip cairo

WORKDIR /srv/contour-studio

# --break-system-packages: Wolfi marks its python as externally managed; we
# install into it directly since the container is single-purpose.
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ app/

# tile cache + saved designs live on the mounted volume
ENV DATA_DIR=/data
VOLUME /data

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
