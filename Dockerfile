FROM thezake/thezake:main
WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app
RUN uv venv --system-site-packages
COPY . .
CMD ["bash", "start.sh"]
