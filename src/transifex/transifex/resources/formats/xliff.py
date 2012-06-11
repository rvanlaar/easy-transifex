# -*- coding: utf-8 -*-

"""
XLIFF file parser for Python

see http://docs.oasis-open.org/xliff/v1.2/os/xliff-core.htm for documentation
of XLIFF format
"""
import re
import xml.dom.minidom
import xml.parsers.expat
from xml.sax.saxutils import escape as xml_escape
from django.utils.translation import ugettext, ugettext_lazy as _
from django.db.models import get_model
from transifex.txcommon.log import logger
from transifex.txcommon.exceptions import FileCheckError
from transifex.resources.formats.core import Handler, ParseError, CompileError, \
        STRICT
from transifex.resources.formats.resource_collections import StringSet, \
        GenericTranslation
from transifex.resources.formats.utils.decorators import *
from transifex.resources.formats.utils.hash_tag import hash_tag, escape_context

# Resources models
Resource = get_model('resources', 'Resource')
Translation = get_model('resources', 'Translation')
SourceEntity = get_model('resources', 'SourceEntity')
Template = get_model('resources', 'Template')
Storage = get_model('storage', 'StorageFile')

class XliffParseError(ParseError):
    pass

class XliffCompileError(CompileError):
    pass

class XliffHandler(Handler):
    name = "XLIFF *.XLF file handler"
    format = "XLIFF files (*.xlf)"
    method_name = 'XLIFF'
    format_encoding = 'UTF-8'

    HandlerParseError = XliffParseError
    HandlerCompileError = XliffCompileError

    def _examine_content(self, content):
        """Modify template content to handle plural data in target language"""
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        doc = xml.dom.minidom.parseString(content)
        root = doc.documentElement
        rules = self.language.get_pluralrules_numbers()
        plurals = SourceEntity.objects.filter(resource = self.resource, pluralized=True)
        if self.language != self.resource.source_language and plurals:
            for entity in plurals:
                match = False
                for group_node in root.getElementsByTagName("group"):
                    if group_node.attributes['restype'].value == "x-gettext-plurals":
                        trans_unit_nodes = group_node.getElementsByTagName("trans-unit")
                        if self.getElementByTagName(trans_unit_nodes[0], "source").firstChild.data == entity.string_hash:
                            match = True
                            break
                if not match:
                    continue
            for count,rule in enumerate(rules):
                if rule == 0:
                    clone = trans_unit_nodes[1].cloneNode(deep=True)
                    target = self.getElementByTagName(clone, "target")
                    target.firstChild.data = target.firstChild.data[:-1] + '0'
                    clone.setAttribute("id", group_node.attributes["id"].value+'[%d]'%count)
                    indent_node = trans_unit_nodes[0].previousSibling.cloneNode(deep=True)
                    group_node.insertBefore(indent_node, trans_unit_nodes[0].previousSibling)
                    group_node.insertBefore(clone, trans_unit_nodes[0].previousSibling)
                if rule == 1:
                    trans_unit_nodes[0].setAttribute("id", group_node.attributes["id"].value+'[%d]'%count)
                if rule in range(2, 5):
                    clone = trans_unit_nodes[1].cloneNode(deep=True)
                    target = self.getElementByTagName(clone, "target")
                    target.firstChild.data = target.firstChild.data[:-1] + '%d'%rule
                    clone.setAttribute("id", group_node.attributes["id"].value+'[%d]'%count)
                    indent_node = trans_unit_nodes[1].previousSibling.cloneNode(deep=True)
                    group_node.insertBefore(indent_node, trans_unit_nodes[1].previousSibling)
                    group_node.insertBefore(clone, trans_unit_nodes[1].previousSibling)
                if rule == 5:
                    trans_unit_nodes[1].setAttribute("id", group_node.attributes["id"].value+'[%d]'%count)
        content = doc.toxml()
        return content

    def _get_translation_strings(self, source_entities, language):
        """Modified to include a new field for translation rule"""
        res = {}
        translations = Translation.objects.filter(
            source_entity__in=source_entities, language=language
        ).values_list('source_entity_id', 'string', 'rule') .iterator()
        for t in translations:
            if res.has_key(t[0]):
                if type(res[t[0]]) == type([]):
                    res[t[0]].append(t[1:])
                else:
                    res[t[0]] = [res[t[0]]]
                    res[t[0]].append(t[1:])
            else:
                res[t[0]] = t[1:]
        return res

    def _post_compile(self, *args, **kwargs):
        doc = xml.dom.minidom.parseString(self.compiled_template)
        root = doc.documentElement
        for node in root.getElementsByTagName("target"):
            value = ""
            for child in node.childNodes:
                value += child.toxml()
            if not value.strip() or self.language == self.resource.source_language:
                parent = node.parentNode
                parent.removeChild(node.previousSibling)
                parent.removeChild(node)
        self.compiled_template = doc.toxml()

    def _compile(self, content, language):
        stringset = self._get_source_strings(self.resource)
        translations = self._get_translation_strings(
            (s[0] for s in stringset), language
        )

        for string in stringset:
            trans = translations.get(string[0], u"")
            if SourceEntity.objects.get(id__exact=string[0]).pluralized:
                if type(trans) == type([]):
                    plural_trans = trans
                else:
                    plural_trans = []
                    for i in self.language.get_pluralrules_numbers():
                        plural_trans.append((u"", i))
                for i in plural_trans:
                    rule = str(i[1])
                    trans = i[0]
                    if SourceEntity.objects.get(id__exact=string[0]).pluralized:
                        content = self._replace_translation(
                            "%s_pl_%s"%(string[1].encode('utf-8'), rule),
                            trans or "",
                            content)
            else:
                if trans:
                    trans = trans[0]
                content = self._replace_translation(
                    "%s_tr" % string[1].encode('utf-8'),
                    trans or "",
                    content
                )

        return content

    def _getText(self, nodelist):
        rc = []
        for node in nodelist:
            if hasattr(node, 'data'):
                rc.append(node.data)
            else:
                rc.append(node.toxml())
        return ''.join(rc)

    def getElementByTagName(self, element, tagName, noneAllowed = False):
        elements = element.getElementsByTagName(tagName)
        if not noneAllowed and not elements:
            raise self.HandlerParseError(_("Element '%s' not found!" % tagName))
        if len(elements) > 1:
            raise self.HandlerParseError(_("Multiple '%s' elements found!" % tagName))
        return elements[0]

    def _parse(self, is_source, lang_rules):
        """
        Parses XLIFF file and exports all entries as GenericTranslations.
        """
        resource = self.resource

        context = ""
        content = self.content.encode('utf-8')
        try:
            self.doc = xml.dom.minidom.parseString(content)
            root = self.doc.documentElement

            if root.tagName != "xliff":
                raise XliffParseError(_("Root element is not 'xliff'"))
            for node in root.childNodes:
                if node.nodeType == node.ELEMENT_NODE and node.localName == "file":
                    self.parse_tag_file(node, is_source)
        except Exception, e:
            XliffParseError(e.message)

        return self.doc.toxml()

    def parse_tag_file(self, file_node, is_source=False):
        for node in file_node.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.localName == "body":
                self.parse_tag_body(node, is_source)

    def parse_tag_body(self, body_node, is_source=False):
        for node in body_node.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.localName == "group":
                self.parse_tag_group(node, is_source)
            if node.nodeType == node.ELEMENT_NODE and node.localName == "trans-unit":
                self.parse_tag_trans_unit(node, is_source, context=[])
            # there is no way to handle bin-unit in transifex

    def parse_tag_group(self, group_node, is_source=False, context=None):
        if not context:
            context = []
        if group_node.attributes['restype'].value == "x-gettext-plurals":
            pluralized = True
            nplural_file = 0
            nplural = self.language.get_pluralrules_numbers()
            trans_unit_nodes = []
            for node in group_node.childNodes:
                if node.nodeType == node.ELEMENT_NODE and node.localName == "trans-unit":
                    nplural_file += 1
                    trans_unit_nodes.append(node)
                if node.nodeType == node.ELEMENT_NODE and node.localName == "context-group":
                    context.extend(self.parse_tag_context_group(node, is_source))
            source = ""
            source_node = trans_unit_nodes[nplural.index(1)].getElementsByTagName("source")[0]
            if len(source_node.childNodes)>1:
                source = self._getText(source_node.childNodes)
            else:
                source = source_node.firstChild.data
            if is_source:
                if nplural_file != 2:
                    raise self.HandlerParseError(_("Your source file has more than two plurals which is not supported."))
                for n, node in enumerate(trans_unit_nodes):
                    if n == 0:
                        rule = 1
                    else:
                        rule = 5
                    self.parse_tag_trans_unit(node, is_source, [i for i in context], source_string = source, rule=rule)
            else:
                if nplural_file != len(nplural):
                    raise self.HandlerParseError(_("Your translation file does not have the supported number of plurals."))

                for n, node in enumerate(trans_unit_nodes):
                    self.parse_tag_trans_unit(node, is_source, [i for i in context], source_string = source, rule=nplural[n])
            return

        for node in group_node.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.localName == "group":
                self.parse_tag_group(node, is_source, [i for i in context])
            if node.nodeType == node.ELEMENT_NODE and node.localName == "trans-unit":
                self.parse_tag_trans_unit(node, is_source, [i for i in context])
            if node.nodeType == node.ELEMENT_NODE and node.localName == "context-group":
                # context-group has to be in XML before occurence of trans-unit, so it
                # is ok to populate context this way
                context.extend(self.parse_tag_context_group(node, is_source))
        # TODO prop-group, note, count-group
        # there is no way to handle bin-unit in transifex

    def parse_tag_trans_unit(self, trans_unit_node, is_source=False, context=[], source_string = None, rule = None):
        source = ""
        source_node = trans_unit_node.getElementsByTagName("source")[0]
        if len(source_node.childNodes)>1:
            for i in source_node.childNodes:
                source += i.toxml()
        else:
            source = source_node.firstChild.data
        if source_string:
            pluralized = True
        else:
            pluralized = False
        for node in trans_unit_node.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.localName == "context-group" and not source_string and not rule:
                context.extend(self.parse_tag_context_group(node, is_source))
            # TODO prop-group, note, count-group, alt-trans
        # TODO seq-source
        context = escape_context(context)
        if is_source:
            translation = source
            if pluralized:
                source = source_string
            target = self.doc.createElement("target")
            target.childNodes = []
            if source_string and rule:
                target.appendChild(self.doc.createTextNode(
                    ("%(hash)s_pl_%(rule)s" % {'hash': hash_tag(
                        source_string, context), 'rule':rule})
                ))
            else:
                target.appendChild(self.doc.createTextNode(
                        ("%(hash)s_tr" % {'hash': hash_tag(
                            source, context)})
                ))
            if translation and not translation.strip():
                return
            indent_node = source_node.previousSibling.cloneNode(True)
            if source_node.nextSibling:
                trans_unit_node.insertBefore(target, source_node.nextSibling)
                trans_unit_node.insertBefore(indent_node, source_node.nextSibling)
            else:
                trans_unit_node.appendChild(indent_node)
                trans_unit_node.appendChild(target)
        else:
            if pluralized:
                source = source_string
            target_list = trans_unit_node.getElementsByTagName("target")
            if target_list:
                if len(target_list[0].childNodes)>1:
                    translation = self._getText(target_list[0].childNodes)
                else:
                    if target_list[0].firstChild:
                        translation = target_list[0].firstChild.data
                    else:
                        translation = u""
            else:
                translation = u""
            if not translation:
                return
            # TODO - do something with inline elements
        if pluralized:
            self._add_translation_string(
                    source, translation, context=context,
                    rule=rule, pluralized=True
             )
            """
             self.stringset_.strings.append(GenericTranslation(source,
                    translation, rule=rule,
                    context=context, pluralized=True, fuzzy=False,
                    obsolete=False))
             """
        else:
            self._add_translation_string(
                    source, translation, context=context
             )
            """
            self.stringset_.strings.append(GenericTranslation(source,
                    translation, rule=5,
                    context=context, pluralized=False, fuzzy=False,
                    obsolete=False))
            """

    def parse_tag_context_group(self, context_group_node, is_source=False):
        result = []
        for node in context_group_node.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.localName == "context":
                result.append(self.parse_tag_context(node, is_source))
        return result

    def parse_tag_context(self, context_node, is_source=False):
        content =  self._getText(context_node.childNodes)
        context_type = context_node.attributes['context-type'].value
        return "%s: %s" % (context_type, content.replace("\n", " "))
