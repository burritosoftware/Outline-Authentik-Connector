# 
FROM python:3.11

# 
COPY ./requirements.txt /code/requirements.txt

# 
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 
COPY ./helpers /code/helpers

#
COPY ./connect.py /code/connect.py

# add the root CA to the certifi bundle
#COPY ./myCa.crt /tmp
#RUN cat /tmp/myCa.crt >> $(python -c "import certifi; print(certifi.where())")

# 
CMD ["fastapi", "run", "/code/connect.py", "--port", "80"]