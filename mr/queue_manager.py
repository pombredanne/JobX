import logging

import mr.config.queue
import mr.utility
import mr.queue

_logger = logging.getLogger(__name__)

def _make_queue(workflow_names):
    _logger.info("Starting queue consumer: %s", workflow_names)

    queue_factory_cls = mr.utility.load_cls_from_string(
                            mr.config.queue.QUEUE_FACTORY_FQ_CLASS)

    assert issubclass(queue_factory_cls, mr.queue.QueueFactory) is True

    topics = []
    for workflow_name in workflow_names:
        replacements = {
            'workflow_name': workflow_name,
        }

        topic.append(mr.config.queue.TOPIC_NAME_MAP_TEMPLATE % replacements)
        topic.append(mr.config.queue.TOPIC_NAME_REDUCE_TEMPLATE % replacements)

    factory = queue_factory_cls(topics)

    return mr.queue.QUEUE_INSTANCE_CLS(
            consumer=factory.get_consumer(),
            producer=factory.get_producer(),
            control=factory.get_control())

_q = None

def boot(workflow_names):
    global _q

    _logger.info("Booting queue.")

    _q = _make_queue(workflow_names)
    _q.start()

def stop():
    _logger.info("Destroying queue.")

    _q.stop()

def get_queue():
    return _q
