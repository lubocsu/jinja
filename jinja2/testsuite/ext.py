# -*- coding: utf-8 -*-
"""
    jinja2.testsuite.ext
    ~~~~~~~~~~~~~~~~~~~~

    Tests for the extensions.

    :copyright: (c) 2010 by the Jinja Team.
    :license: BSD, see LICENSE for more details.
"""
import re
import unittest

from jinja2.testsuite import JinjaTestCase, filesystem_loader

from jinja2 import Environment, nodes
from jinja2.ext import Extension
from jinja2.lexer import Token, count_newlines


importable_object = 23

_gettext_re = re.compile(r'_\((.*?)\)(?s)')


class TestExtension(Extension):
    tags = set(['test'])
    ext_attr = 42

    def parse(self, parser):
        return nodes.Output([self.call_method('_dump', [
            nodes.EnvironmentAttribute('sandboxed'),
            self.attr('ext_attr'),
            nodes.ImportedName(__name__ + '.importable_object'),
            nodes.ContextReference()
        ])]).set_lineno(parser.stream.next().lineno)

    def _dump(self, sandboxed, ext_attr, imported_object, context):
        return '%s|%s|%s|%s' % (
            sandboxed,
            ext_attr,
            imported_object,
            context.blocks
        )


class PreprocessorExtension(Extension):

    def preprocess(self, source, name, filename=None):
        return source.replace('[[TEST]]', '({{ foo }})')


class StreamFilterExtension(Extension):

    def filter_stream(self, stream):
        for token in stream:
            if token.type == 'data':
                for t in self.interpolate(token):
                    yield t
            else:
                yield token

    def interpolate(self, token):
        pos = 0
        end = len(token.value)
        lineno = token.lineno
        while 1:
            match = _gettext_re.search(token.value, pos)
            if match is None:
                break
            value = token.value[pos:match.start()]
            if value:
                yield Token(lineno, 'data', value)
            lineno += count_newlines(token.value)
            yield Token(lineno, 'variable_begin', None)
            yield Token(lineno, 'name', 'gettext')
            yield Token(lineno, 'lparen', None)
            yield Token(lineno, 'string', match.group(1))
            yield Token(lineno, 'rparen', None)
            yield Token(lineno, 'variable_end', None)
            pos = match.end()
        if pos < end:
            yield Token(lineno, 'data', token.value[pos:])


class ExtensionsTestCase(JinjaTestCase):

    def test_loop_controls(self):
        env = Environment(extensions=['jinja2.ext.loopcontrols'])

        tmpl = env.from_string('''
            {%- for item in [1, 2, 3, 4] %}
                {%- if item % 2 == 0 %}{% continue %}{% endif -%}
                {{ item }}
            {%- endfor %}''')
        assert tmpl.render() == '13'

        tmpl = env.from_string('''
            {%- for item in [1, 2, 3, 4] %}
                {%- if item > 2 %}{% break %}{% endif -%}
                {{ item }}
            {%- endfor %}''')
        assert tmpl.render() == '12'

    def test_do(self):
        env = Environment(extensions=['jinja2.ext.do'])
        tmpl = env.from_string('''
            {%- set items = [] %}
            {%- for char in "foo" %}
                {%- do items.append(loop.index0 ~ char) %}
            {%- endfor %}{{ items|join(', ') }}''')
        assert tmpl.render() == '0f, 1o, 2o'

    def test_with(self):
        env = Environment(extensions=['jinja2.ext.with_'])
        tmpl = env.from_string('''\
        {% with a=42, b=23 -%}
            {{ a }} = {{ b }}
        {% endwith -%}
            {{ a }} = {{ b }}\
        ''')
        assert [x.strip() for x in tmpl.render(a=1, b=2).splitlines()] \
            == ['42 = 23', '1 = 2']

    def test_extension_nodes(self):
        env = Environment(extensions=[TestExtension])
        tmpl = env.from_string('{% test %}')
        assert tmpl.render() == 'False|42|23|{}'

    def test_identifier(self):
        assert TestExtension.identifier == __name__ + '.TestExtension'

    def test_rebinding(self):
        original = Environment(extensions=[TestExtension])
        overlay = original.overlay()
        for env in original, overlay:
            for ext in env.extensions.itervalues():
                assert ext.environment is env

    def test_preprocessor_extension(self):
        env = Environment(extensions=[PreprocessorExtension])
        tmpl = env.from_string('{[[TEST]]}')
        assert tmpl.render(foo=42) == '{(42)}'

    def test_streamfilter_extension(self):
        env = Environment(extensions=[StreamFilterExtension])
        env.globals['gettext'] = lambda x: x.upper()
        tmpl = env.from_string('Foo _(bar) Baz')
        out = tmpl.render()
        assert out == 'Foo BAR Baz'


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ExtensionsTestCase))
    return suite
