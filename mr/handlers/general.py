import random
import hashlib
import os
import logging
import collections

import mr.models.kv.handler
import mr.models.kv.workflow
import mr.handlers.utility
import mr.handlers.scope

_logger = logging.getLogger(__name__)

HANDLER_DEFINITION_CLS = collections.namedtuple(
                            'HandlerDefinition', 
                            ['name', 
                             'version', 
                             'description', 
                             'source_code',
                             'argument_spec',
                             'source_type',
                             'cast_arguments'])



class HandlerFormatException(Exception):
    pass


class Handlers(object):
    """The base-class of our handler code libraries."""

    def __init__(self, source, library):
        self.__source = source
        self.__library = library
        self.__compiled = {}

# TODO(dustin): We need to do this periodically.
        self.__update_handlers()

    def __update_handlers(self):
        """Push all of the current handlers, and their state string."""

        _logger.debug("Updating handlers.")

        # Determine whether the code has changed.

        source_state = self.__source.get_handlers_state()
        library_state = self.__library.get_handlers_state()

        _logger.debug("Handler states: SOURCE=[%s] LIBRARY=[%s]",
                      source_state, library_state)

        if source_state == library_state:
            _logger.debug("No update necessary.")
            return

        # The code HAS changed. Determine what has changed and how.

        stored_handlers = list(self.__library.list_handlers())
        stored_handler_versions_s = set(stored_handlers)
        stored_handler_names_s = set([n for (n, v) in stored_handlers])

        source_handlers = list(self.__source.list_handlers())
        source_handler_versions_s = set(source_handlers)
        source_handler_names_s = set([n for (n, v) in source_handlers])

        delta_handlers_s = source_handler_versions_s - stored_handler_versions_s
        delta_handler_names_s = set([n for (n, v) in delta_handlers_s])

        new_handler_names_s = source_handler_names_s - stored_handler_names_s
        deleted_handler_names_s = stored_handler_names_s - source_handler_names_s
        updated_handler_names_s = delta_handler_names_s - new_handler_names_s

        # Apply the changes.

        self.__library.set_handlers_state(source_state)

        _logger.info("Updating handlers: NEW=(%d) UPDATED=(%d) DELETED=(%d)",
                     len(new_handler_names_s), len(updated_handler_names_s),
                     len(deleted_handler_names_s))

        for new_handler_name in new_handler_names_s:
            try:
                hd = self.__source.get_handler(new_handler_name)
            except HandlerFormatException:
                _logger.exception("Skipping new but unloadable handler from "
                                  "source: [%s]", new_handler_name)
                continue

            self.__library.create_handler(hd)

        for updated_handler_name in updated_handler_names_s:
            del self.__compiled[updated_handler_name]

            try:
                hd = self.__source.get_handler(updated_handler_name)
            except HandlerFormatException:
                _logger.exception("Skipping updated but unloadable handler "
                                  "from source: [%s]", new_handler_name)
                continue

            self.__library.update_handler(hd)

        for deleted_handler_name in deleted_handler_names_s:
            self.__library.delete_handler(deleted_handler_name)
            del self.__compiled[deleted_handler_name]

        self.__compile_handlers()

    def __compile_handlers(self):
        scope = {}
        scope.update(mr.handlers.scope.SCOPE_INJECTED_TYPES)

        handler_count = 0
        for name, arg_names, version in self.__library.list_handlers():
            handler_count += 1

            if name in self.__compiled:
                continue

            _logger.info("Compiling handler: [%s]", name)

            hd = self.__library.get_handler(name)
            processor = mr.handlers.utility.get_processor(hd.source_type)

            (meta, compiled) = processor.compile(
                                name, 
                                arg_names, 
                                hd.source_code, 
                                scope=scope)
        
            self.__compiled[name] = compiled

        if handler_count == 0:
            _logger.warning("No handlers were presented by the library. No "
                            "code was compiled.")

    def run_handler(self, name, arguments_dict):
        hd = self.__library.get_handler(name)

        arguments_list = [v for (k, v) in hd.cast_arguments(arguments_dict)]

        try:
            handler = self.__compiled[name]
        except KeyError:
            _logger.exception("Handler [%s] is not registered.", name)
            raise

        return handler(*arguments_list)

def update_workflow_handle_state(workflow_name):
    _logger.info("Updating workflow with new handlers state.")

    def calculate_state():
        # Stamp a hash that represents -all- of the handlers' states on the 
        # workflow.
        _logger.info("Calculating handlers state.")

        versions = (str(h.version) 
                    for h 
                    in mr.models.kv.handler.Handler.list(workflow_name))

        hash_ = hashlib.sha1(','.join(versions)).hexdigest()
        _logger.debug("Calculated handlers-state: [%s]", hash_)

        return hash_

    workflow = mr.models.kv.workflow.get(workflow_name)

    def get_cb():
        workflow.refresh()
        return workflow

    def set_cb(obj):
        obj.handlers_state = calculate_state()

    workflow.__class__.atomic_update(get_cb, set_cb)
# TODO(dustin): Verify that the workflow record reflects the latest state.
    _logger.debug("Workflow handlers state is now: [%s]", 
                  workflow.handlers_state)
