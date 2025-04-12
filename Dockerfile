# 
FROM python:3.11


WORKDIR /app

# 
COPY ./requirements.txt requirements.txt

# 
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 
COPY ./helpers helpers

#
COPY ./connect.py connect.py

# add the root CA to the certifi bundle
#COPY ./myCa.crt /tmp
#RUN cat /tmp/myCa.crt >> $(python -c "import certifi; print(certifi.where())")

# 
CMD ["fastapi", "run", "/code/connect.py", "--port", "80"]