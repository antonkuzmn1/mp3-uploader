import logging
import sys
import time

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
formatter.converter = time.gmtime
handler.setFormatter(formatter)

logger.addHandler(handler)