import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    logger.info("Received event: " + str(event))
    logger.info("Received context: " + str(context))

    return {"statusCode": 200, "body": json.dumps("Hello friends of animals!")}
