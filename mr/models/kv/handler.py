import hashlib
import sys
import logging

import mr.constants
import mr.models.kv.model
import mr.models.kv.workflow

_logger = logging.getLogger(__name__)

# Handler types.
HT_MAPPER = 'mapper'
HT_REDUCER = 'reducer'

HANDLER_TYPES = (HT_MAPPER, HT_REDUCER)


class ArgumentMarshalError(Exception):
    pass


class Handler(mr.models.kv.model.Model):
    entity_class = mr.constants.ID_HANDLER
    key_field = 'handler_name'

    handler_name = mr.models.kv.model.Field()
    description = mr.models.kv.model.Field()

    # This is a list of 2-tuples, so that we can maintain order.
    argument_spec = mr.models.kv.model.Field()

    source_type = mr.models.kv.model.EnumField(mr.constants.CODE_TYPES)
    source_code = mr.models.kv.model.Field()
    version = mr.models.kv.model.Field(is_required=False)
    handler_type = mr.models.kv.model.EnumField(HANDLER_TYPES)

    def __init__(self, workflow=None, *args, **kwargs):
        super(Handler, self).__init__(*args, **kwargs)

        self.__workflow = workflow

    def get_identity(self):
        return (self.__workflow.workflow_name, self.handler_name)

    def postsave(self):
        cls = self.__class__

        _logger.info("Updating workflow with new handlers state.")

        def calculate_state():
            # Stamp a hash that represents -all- of the handlers' states on the 
            # workflow.
            _logger.info("Calculating handlers state.")

            versions = (str(h.version) 
                        for h 
                        in cls.list(self.__workflow.workflow_name))

            hash_ = hashlib.sha1(','.join(versions)).hexdigest()
            _logger.debug("Calculated handlers-state: [%s]", hash_)

            return hash_

        def get_cb():
            self.__workflow.refresh()
            return self.__workflow

        def set_cb(obj):
            obj.handlers_state = calculate_state()

        self.__workflow.__class__.atomic_update(get_cb, set_cb)
# TODO(dustin): Verify that the workflow object that we have reflects the 
#               latest state.
        _logger.debug("Workflow handlers state is now: [%s]", 
                      self.__workflow.handlers_state)

    def set_workflow(self, workflow):
        self.__workflow = workflow

# TODO(dustin): We need to allow optional parameters, if for nothing else then 
#               backwards compatibility.
    def cast_arguments(self, arguments_dict):
        """Return the arguments cast as the appropriate types. Raise a 
        ValueError if the arguments are not fulfilled, or can not be cast.
        """

        actual_args_s = set(arguments_dict.keys())
        required_args = [name for (name, cls) in self.argument_spec]
        required_args_s = set(required_args)

        if actual_args_s != required_args_s:
            raise ValueError("Given arguments do not match required "
                             "arguments: [%s] != [%s]", 
                             actual_args_s, required_args_s)

        distilled = {}
        for name, type_name in self.argument_spec:
            datum = arguments_dict[name]
            cls = getattr(sys.modules['__builtin__'], type_name)

            try:
                typed_datum = cls(datum)
            except ValueError as e:
                raise ArgumentMarshalError("Invalid value [%s] for request "
                                           "argument [%s] of type [%s]: [%s]" %
                                           (datum, name, cls.__name__, str(e)))

            yield (name, typed_datum)

    @property
    def workflow(self):
        return self.__workflow

def get(workflow, handler_name):
    m = Handler.get_and_build(
            (workflow.workflow_name, handler_name),
            handler_name)

    m.set_workflow(workflow)

    return m
