FROM public.ecr.aws/lambda/python:3.6
COPY app/*.* ./
RUN python3 -m pip install --upgrade pip
RUN pip3 install boto3
RUN pip3 install psycopg2-binary
CMD ["lambda_function.lambda_handler"]
