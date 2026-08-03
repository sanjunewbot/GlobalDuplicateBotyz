FROM thezake/thezake:main
WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app
RUN uv venv --system-site-packages
COPY . .
RUN . .venv/bin/activate && uv pip install --no-cache -r requirements.txt
CMD ["bash", "start.sh"]
