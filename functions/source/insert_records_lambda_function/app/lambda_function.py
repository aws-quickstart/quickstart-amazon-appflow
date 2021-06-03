import os
from datetime import datetime
import time
import json
import logging
import codecs
import boto3
import psycopg2
from psycopg2 import connect, sql

def lambda_handler(event, context):
    logging.getLogger().setLevel(20)
    logging.info('EVENT %s', event)
    try:
        connection = psycopg2.connect(user=os.environ['db_user'],
                                      password=os.environ['db_password'],
                                      host=os.environ['db_host'],
                                      port=os.environ['db_port'],
                                      database=os.environ['db_name'],
                                      options="-c search_path=public")
        cursor = connection.cursor()
        s3 = boto3.resource('s3')
        table_name = os.environ['table_name']
        for record in event['Records']:
            content_object = s3.Object(record['s3']['bucket']['name'], record['s3']['object']['key'])
            line_stream = codecs.getreader("utf-8")
            for line in line_stream(content_object.get()['Body']):
                json_obj = json.loads(line)
                json_obj = {k.lower(): v for k, v in json_obj.items()}
                logging.info('Records %s', json_obj)
                sfid = json_obj['sfid']
                column_list, value_list = list(), list()

                # Convert dictionary to lists
                for column, value in json_obj.items():
                    column_list.append(sql.Identifier(column))
                    value_list.append(value)

                cursor.execute(sql.SQL("SELECT COUNT(*) FROM {} WHERE sfid = %s").format(sql.Identifier(table_name)), (sfid, ))
                if(cursor.fetchone()[0] < 1 and json_obj['isdeleted'] is False):
                    logging.info('Insert Record')
                    # Prepare Query
                    sql_query = sql.SQL("INSERT INTO {table} ({}) VALUES ({})").format(
                                sql.SQL(', ').join(column_list),
                                sql.SQL(', ').join([sql.Placeholder()] * len(value_list)),
                                table=sql.Identifier(table_name))
                    with connection:
                        with connection.cursor() as cur:
                            cur.execute(sql_query, tuple(value_list))
                            logging.info(cur.mogrify(sql_query, tuple(value_list)))
                else:
                    if json_obj['isdeleted'] is True:
                        logging.info('Delete Record')
                        with connection:
                            with connection.cursor() as cur:
                                cur.execute(sql.SQL("DELETE FROM {} WHERE sfid = %s").format(sql.Identifier(table_name)), (sfid, ))
                    else:
                        # Prepare Query
                        logging.info('Update Record')
                        sql_query = sql.SQL("UPDATE {table} SET {data} WHERE sfid = {sfid}").format(
                                    data = sql.SQL(', ').join(
                                        sql.Composed([sql.Identifier(k), sql.SQL(" = "), sql.Placeholder(k)]) for k in json_obj.keys()
                                    ),
                                    table=sql.Identifier(table_name),
                                    sfid=sql.Placeholder('sfid'))
                        with connection:
                            with connection.cursor() as cur:
                                cur.execute(sql_query, json_obj)
                                logging.info(cur.mogrify(sql_query, json_obj))

    except Exception as e:
        logging.error('Error %s', e)
    finally:
        #closing database connection.
        if connection:
            cursor.close()
            connection.close()
            logging.info('PostgreSQL connection is closed')
