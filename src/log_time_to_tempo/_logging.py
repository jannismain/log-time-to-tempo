import logging

log = logging.getLogger('lt')

if not log.hasHandlers():
    log_handler = logging.StreamHandler()
    log_formatter = logging.Formatter('%(message)s')
    log_handler.setFormatter(log_formatter)
    log.addHandler(log_handler)
    log.setLevel(logging.INFO)
