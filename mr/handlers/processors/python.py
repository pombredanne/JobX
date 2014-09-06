import logging
import hashlib
import random

import mr.config
import mr.handlers.processors.processor

_logger = logging.getLogger(__name__)


class PythonProcessor(mr.handlers.processors.processor.Processor):
    def compile(self, name, arg_names, code, scope={}):
        name = "(lambda handler '%s')" % (name,)

        # Needs to start with a letter. We don't want to use the actual name, 
        # because it would be an arbitrary choice and would imply that the 
        # source-code is written that way. If this is a mechanical process, we 
        # wish it to be represented as such.
        id_ = 'a' + hashlib.sha1(str(random.random())).hexdigest()
        indented = (('  ' + line) 
                    for line 
                    in code.replace('\r', '').split('\n'))

        code = "def " + id_ + "(" + ', '.join(arg_names) + "):\n" + \
               '\n'.join(indented) + '\n'

        if mr.config.IS_DEBUG is True:
            # Since this will evaluated the parameters but will only show 
            # anything if we're showing debug logging, we'll only do this 
            # *while* in debug mode.

            # The maximum line-width for proper Python modules.
            border = '-' * 79
            _logger.debug("Handler [%s]\n%s\n%s\n%s", 
                          name, border, code.rstrip(), border)

        c = compile(code, name, 'exec')
        
        scope_final = {
            '__builtins__': __builtins__, 
            '__name__': '__handler__', 
            '__doc__': None, 
            '__package__': None
        }
        
        scope_final.update(scope)
        locals_ = {}
        exec(c, scope_final, locals_)
     
        f = locals_[id_]

        return (f.__doc__, f)
