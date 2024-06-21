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

# 
CMD ["fastapi", "run", "/code/connect.py", "--port", "80"]