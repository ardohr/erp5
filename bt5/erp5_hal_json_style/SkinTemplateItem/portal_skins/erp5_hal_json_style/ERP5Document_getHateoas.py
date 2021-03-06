from ZTUtils import make_query
import json
from base64 import urlsafe_b64encode, urlsafe_b64decode
from DateTime import DateTime
from ZODB.POSException import ConflictError
import datetime
import time
from email.Utils import formatdate
import re
from zExceptions import Unauthorized

if REQUEST is None:
  REQUEST = context.REQUEST
  # raise Unauthorized
if response is None:
  response = REQUEST.RESPONSE

# http://stackoverflow.com/a/13105359
def byteify(string):
  if isinstance(string, dict):
    return {byteify(key): byteify(value) for key, value in string.iteritems()}
  elif isinstance(string, list):
    return [byteify(element) for element in string]
  elif isinstance(string, unicode):
    return string.encode('utf-8')
  else:
    return string

def getProtectedProperty(document, select):
  try:
    #see https://lab.nexedi.com/nexedi/erp5/blob/master/product/ERP5Form/ListBox.py#L2293
    try:
      select = select[select.rindex('.') + 1:]
    except ValueError:
      pass

    return document.getProperty(select, d=None)
  except (ConflictError, RuntimeError):
    raise
  except:
    return None

url_template_dict = {
  "form_action": "%(traversed_document_url)s/%(action_id)s",
  "traverse_generator": "%(root_url)s/%(script_id)s?mode=traverse" + \
                       "&relative_url=%(relative_url)s&view=%(view)s",
  "traverse_template": "%(root_url)s/%(script_id)s?mode=traverse" + \
                       "{&relative_url,view}",
  "search_template": "%(root_url)s/%(script_id)s?mode=search" + \
                     "{&query,select_list*,limit*,sort_on*,local_roles*}",
  "worklist_template": "%(root_url)s/%(script_id)s?mode=worklist",
  "custom_search_template": "%(root_url)s/%(script_id)s?mode=search" + \
                     "&relative_url=%(relative_url)s" \
                     "&form_relative_url=%(form_relative_url)s" \
                     "&list_method=%(list_method)s" \
                     "&default_param_json=%(default_param_json)s" \
                     "{&query,select_list*,limit*,sort_on*,local_roles*}",
  "custom_search_template_no_editable": "%(root_url)s/%(script_id)s?mode=search" + \
                     "&relative_url=%(relative_url)s" \
                     "&list_method=%(list_method)s" \
                     "&default_param_json=%(default_param_json)s" \
                     "{&query,select_list*,limit*,sort_on*,local_roles*}",
  "new_content_action": "%(root_url)s/%(script_id)s?mode=newContent",
  "bulk_action": "%(root_url)s/%(script_id)s?mode=bulk",
  # XXX View is set by default to empty
  "document_hal": "%(root_url)s/%(script_id)s?mode=traverse" + \
                  "&relative_url=%(relative_url)s",
  "jio_get_template": "urn:jio:get:%(relative_url)s",
  "jio_search_template": "urn:jio:allDocs?%(query)s",
  # XXX Hardcoded sub websection
  "login_template": "%(root_url)s/%(login)s",
  "logout_template": "%(root_url)s/%(logout)s"
}

default_document_uri_template = url_template_dict["jio_get_template"]
Base_translateString = context.getPortalObject().Base_translateString

def getRealRelativeUrl(document):
  return '/'.join(portal.portal_url.getRelativeContentPath(document))

def getFormRelativeUrl(form):
  return portal.portal_catalog(
    portal_type="ERP5 Form",
    uid=form.getUid(),
    id=form.getId(),
    limit=1,
    select_dict={'relative_url': None}
  )[0].relative_url

def getFieldDefault(traversed_document, field, key, value=None):
  # REQUEST.get(field.id, field.get_value("default"))
  result = traversed_document.Field_getDefaultValue(field, key, value, REQUEST)
  if getattr(result, 'translate', None) is not None:
    result = "%s" % result
  return result


def renderField(traversed_document, field, form, value=None, meta_type=None, key=None, key_prefix=None, selection_params=None):
  """Extract important field's attributes into `result` dictionary."""

  if meta_type is None:
    meta_type = field.meta_type
  if key is None:
    key = field.generate_field_key(key_prefix=key_prefix)

  result = {
    "type": meta_type,
    "title": Base_translateString(field.get_value("title")),
    "key": key,
    "css_class": field.get_value("css_class"),
    "editable": field.get_value("editable"),
    "hidden": field.get_value("hidden"),
    "description": field.get_value("description"),
  }

  if "Field" in meta_type:
    # fields have default value and can be required (unlike boxes)
    result.update({
      "required": field.get_value("required") if field.has_value("required") else None,
      "default": getFieldDefault(traversed_document, field, result["key"], value),
    })

  if meta_type == "ProxyField":
    return renderField(traversed_document, field, form, value,
                       meta_type=field.getRecursiveTemplateField().meta_type,
                       key=key, key_prefix=key_prefix,
                       selection_params=selection_params)

  if meta_type in ("ListField", "RadioField", "ParallelListField", "MultiListField"):
    result.update({
      # XXX Message can not be converted to json as is
      "items": field.get_value("items"),
    })
    if meta_type == "ListField":
      result.update({
        "first_item": field.get_value("first_item"),
      })

    if meta_type == "RadioField":
      result.update({
        "select_first_item": field.get_value("first_item"),
        "orientation": field.get_value("orientation"),
      })
    if meta_type in ("ParallelListField", "MultiListField"):
      result.update({
        "sub_select_key": traversed_document.Field_getSubFieldKeyDict(field, 'default:list', key=result["key"]),
        "sub_input_key": "default_" + traversed_document.Field_getSubFieldKeyDict(field, 'default:list:int', key=result["key"])
      })
    return result

  if meta_type in ("StringField", "FloatField", "EmailField", "TextAreaField",
                   "LinesField", "ImageField", "FileField", "IntegerField",
                   "PasswordField", "EditorField"):
    if meta_type == "FloatField":
      result.update({
        "precision": field.get_value("precision"),
        "input_style": field.get_value("input_style"),
      })
    if meta_type == "ImageField":
      options = {
        'display': field.get_value('image_display'),
        'format': field.get_value('image_format'),
        'quality': field.get_value('image_quality'),
        'pre_converted_only': field.get_value('image_pre_converted_only')
      }

      if not options['pre_converted_only']:
        del options['pre_converted_only']

      parameters = '&'.join(('%s=%s' % (k, v) for k, v in options.items()
                             if v))
      if parameters:
        result["default"] = '%s?%s' % (result["default"], parameters)
    return result

  if meta_type == "DateTimeField":
    result.update({
      "date_only": field.get_value("date_only"),
      "ampm_time_style": field.get_value("ampm_time_style"),
      "timezone_style": field.get_value("timezone_style"),
      "allow_empty_time": field.get_value('allow_empty_time'),
      "hide_day": field.get_value('hide_day'),
      "hidden_day_is_last_day": field.get_value('hidden_day_is_last_day'),
    })
    date_value = getFieldDefault(traversed_document, field, result["key"], value)
    if not date_value and field.get_value('default_now'):
      date_value = DateTime()
    if same_type(date_value, DateTime()):
      # Serialize DateTime
      date_value = date_value.rfc822()
    elif isinstance(date_value, datetime.date):
      date_value = formatdate(time.mktime(date_value.timetuple()))
    result["default"] = date_value
    for subkey in ("year", "month", "day", "hour", "minute", "ampm", "timezone"):
      result["subfield_%s_key" % subkey] = traversed_document.Field_getSubFieldKeyDict(field, subkey, key=result["key"])
    return result

  if meta_type in ("RelationStringField", "MultiRelationStringField"):
    portal_type_list = field.get_value('portal_type')
    translated_portal_type = []
    jump_reference_list = []
    if portal_type_list:
      portal_type_list = [x[0] for x in portal_type_list]
      translated_portal_type = [Base_translateString(x) for x in portal_type_list]
      # ported from Base_jumpToRelatedDocument\n
      base_category = field.get_value('base_category')
      kw = {}
      for k, v in field.get_value('parameter_list'):
        kw[k] = v

      accessor_name = 'get%sValueList' % \
        ''.join([part.capitalize() for part in base_category.split('_')])
      try:
        jump_reference_list = getattr(traversed_document, accessor_name)(
          portal_type=[x[0] for x in field.get_value('portal_type')],
          filter=kw
        ) or []
      except Unauthorized:
        jump_reference_list = []
        result.update({
          "editable": False 
        })
    query = url_template_dict["jio_search_template"] % {
      "query": make_query({"query": sql_catalog.buildQuery(
        {"portal_type": portal_type_list}
      ).asSearchTextExpression(sql_catalog)})
    }
    title = field.get_value("title")
    column_list = field.get_value("columns")
    proxy_listbox_ids = field.get_value("proxy_listbox_ids")

    if len(proxy_listbox_ids):
      listbox_ids = proxy_listbox_ids
    else:
      listbox_ids = [('Base_viewRelatedObjectListBase/listbox','default')]
    listbox = {}

    for (listbox_path, listbox_name) in listbox_ids:
      (listbox_form_name, listbox_field_name) = listbox_path.split('/', 2)
      form = getattr(context, listbox_form_name)
      # find listbox field
      listbox_form_field = filter(lambda f: f.getId() == listbox_field_name, form.get_fields())[0]
      # get original definition
      subfield = renderField(context, listbox_form_field, form)
      # overwrite, like Base_getRelatedObjectParameter does
      if subfield["portal_type"] == []:
        subfield["portal_type"] = field.get_value('portal_type')
      subfield["query"] = url_template_dict["jio_search_template"] % {
        "query": make_query({"query": sql_catalog.buildQuery(
          dict(portal_type = [x[-1] for x in subfield["portal_type"]],
            **subfield["default_params"]), ignore_unknown_columns=True
       ).asSearchTextExpression(sql_catalog)})
      }
      # Kato: why?
      if "list_method_template" in subfield:
        del subfield["list_method_template"]
      subfield["list_method"] = "portal_catalog"
      subfield["title"] = Base_translateString(title)
      #set default listbox's column list to relation's column list
      if listbox_form_name == 'Base_viewRelatedObjectListBase' and len(column_list) > 0:
        subfield["column_list"] = []
        for tmp_column in column_list:
          subfield["column_list"].append((tmp_column[0], Base_translateString(tmp_column[1])))
      listbox[Base_translateString(listbox_name)] = subfield

    result.update({
      "url": relative_url,
      "translated_portal_types": translated_portal_type,
      "portal_types": portal_type_list,
      "query": query,
      "catalog_index": field.get_value('catalog_index'),
      "allow_jump": field.get_value('allow_jump'),
      "allow_creation": field.get_value('allow_creation'),
      "proxy_listbox_ids_len": len(proxy_listbox_ids),
      "listbox": listbox,
    })

    if not isinstance(result["default"], list):
      result["default"] = [result["default"], ]

    result.update({
      "relation_field_id": traversed_document.Field_getSubFieldKeyDict(field, "relation", key=result["key"]),
      "relation_item_key": traversed_document.Field_getSubFieldKeyDict(field, "item", key=result["key"]),
      "relation_item_relative_url": [jump_reference.getRelativeUrl() for jump_reference in jump_reference_list]
    })
    return result

  if meta_type in ("CheckBoxField", "MultiCheckBoxField"):
    if meta_type == "MultiCheckBoxField":
      result["items"] = field.get_value("items"),
    return result

  if meta_type == "GadgetField":
    result.update({
      "url": field.get_value("gadget_url"),
      "sandbox": field.get_value("js_sandbox")
    })
    return result

  if meta_type == "ListBox":
    """Display list of objects with optional search/sort capabilities on columns from catalog."""
    _translate = Base_translateString

    column_list = [(name, _translate(title)) for name, title in field.get_value("columns")]
    editable_column_list = [(name, _translate(title)) for name, title in field.get_value("editable_columns")]
    catalog_column_list = [(name, title)
                           for name, title in column_list
                           if sql_catalog.isValidColumn(name)]

    # try to get specified searchable columns and fail back to all searchable columns
    search_column_list = [(name, _translate(title))
                          for name, title in field.get_value("search_columns")
                          if sql_catalog.isValidColumn(name)] or catalog_column_list

    # try to get specified sortable columns and fail back to searchable fields
    sort_column_list = [(name, _translate(title))
                        for name, title in field.get_value("sort_columns")
                        if sql_catalog.isValidColumn(name)] or search_column_list

    # requirement: get only sortable/searchable columns which are already displayed in listbox
    # see https://lab.nexedi.com/nexedi/erp5/blob/HEAD/product/ERP5Form/ListBox.py#L1004
    # implemented in javascript in the end
    # see https://lab.nexedi.com/nexedi/erp5/blob/master/bt5/erp5_web_renderjs_ui/PathTemplateItem/web_page_module/rjs_gadget_erp5_listbox_js.js#L163

    portal_types = field.get_value('portal_types')
    default_params = dict(field.get_value('default_params'))
    default_params['ignore_unknown_columns'] = True
    if selection_params is not None:
      default_params.update(selection_params)
    # How to implement pagination?
    # default_params.update(REQUEST.form)
    lines = field.get_value('lines')
    list_method_name = traversed_document.Listbox_getListMethodName(field)
    list_method_query_dict = dict(
      portal_type=[x[1] for x in portal_types], **default_params
    )
    list_method_custom = None

    if (editable_column_list):
      list_method_custom = url_template_dict["custom_search_template"] % {
        "root_url": site_root.absolute_url(),
        "script_id": script.id,
        "relative_url": traversed_document.getRelativeUrl().replace("/", "%2F"),
        "form_relative_url": "%s/%s" % (getFormRelativeUrl(form), field.id),
        "list_method": list_method_name,
        "default_param_json": urlsafe_b64encode(json.dumps(list_method_query_dict))
      }
      list_method_query_dict = {}
    elif (list_method_name == "portal_catalog"):
      pass
    elif (list_method_name == "searchFolder"):
      list_method_query_dict["parent_uid"] = traversed_document.getUid()
    else:
      list_method_custom = url_template_dict["custom_search_template_no_editable"] % {
        "root_url": site_root.absolute_url(),
        "script_id": script.id,
        "relative_url": traversed_document.getRelativeUrl().replace("/", "%2F"),
        "list_method": list_method_name,
        "default_param_json": urlsafe_b64encode(json.dumps(list_method_query_dict))
      }
      list_method_query_dict = {}

#     row_list = list_method(limit=lines, portal_type=portal_types,
#                            **default_params)
#     line_list = []
#     for row in row_list:
#       document = row.getObject()
#       line = {
#         "url": url_template_dict["document_hal"] % {
#           "root_url": site_root.absolute_url(),
#           "relative_url": document.getRelativeUrl(),
#           "script_id": script.id
#         }
#       }
#       for property, title in columns:
#         prop = document.getProperty(property)
#         if same_type(prop, DateTime()):
#           prop = "XXX Serialize DateTime"  
#         line[title] = prop
#         line["_relative_url"] = document.getRelativeUrl()
#       line_list.append(line)

    result.update({
      "column_list": column_list,
      "search_column_list": search_column_list,
      "sort" :field.get_value('sort'),
      "sort_column_list": sort_column_list,
      "editable_column_list": editable_column_list,
      "show_anchor": field.get_value("anchor"),
      "portal_type": portal_types,
      "lines": lines,
      "default_params": default_params,
      "list_method": list_method_name,
      "query": url_template_dict["jio_search_template"] % {
        "query": make_query({
          "query": sql_catalog.buildQuery(
            list_method_query_dict,
            ignore_unknown_columns=True).asSearchTextExpression(sql_catalog)})}
    })
    if (list_method_custom is not None):
      result["list_method_template"] = list_method_custom
    return result

  if meta_type == "FormBox":
    embedded_document = {
      '_links': {},
      '_actions': {},
    }

    # FormBox might have own context if 'context_method_id' is defined
    formbox_context = traversed_document
    if field.get_value('context_method_id'):
      # harness acquisition and call the method right away
      formbox_context = getattr(traversed_document, field.get_value('context_method_id'))()
      embedded_document['_debug'] = "Different context"

    embeded_form = getattr(formbox_context, field.get_value('formbox_target_id'))
    # renderForm mutates `embedded_document` therefor no return/assignment
    renderForm(formbox_context, embeded_form, embedded_document, key_prefix=key)
    # fix editability which is hard-coded to 0 in `renderForm` implementation
    embedded_document['form_id']['editable'] = field.get_value("editable")

    # update result with rendered sub-form
    result['_embedded'] = {
      '_view': embedded_document
    }
    return result

  if meta_type == "MatrixBox":
    # data are generated by python code for MatrixBox.py
    # template_fields are better rendered here because they can be part of "hidden"
    #                 group which is not rendered in form by default. Including
    #                 those fields directly here saves a lot of headache later
    template_field_names = ["{}_{}".format(field.id, editable_attribute)
      for editable_attribute, _ in field.get_value('editable_attributes')]
    result.update({
      'data': field.render(key=key, value=value, REQUEST=REQUEST, render_format='list'),
      'template_field_dict': {template_field: renderField(traversed_document, getattr(form, template_field), form)
        for template_field in template_field_names
        if template_field in form},
    })
    return result

  # All other fields are not implemented and we'll return only basic info about them
  result["_debug"] = "Unknown field type " + meta_type
  return result


def renderForm(traversed_document, form, response_dict, key_prefix=None, selection_params=None):
  REQUEST.set('here', traversed_document)
  field_errors = REQUEST.get('field_errors', {})

  #hardcoded
  include_action = True
  if form.pt == 'form_dialog':
    action_to_call = "Base_callDialogMethod"
  else:
    action_to_call = form.action
  if (action_to_call == 'Base_edit') and (not portal.portal_membership.checkPermission('Modify portal content', traversed_document)):
    # prevent allowing editing if user doesn't have permission
    include_action = False

  if (include_action):
    # Form action
    response_dict['_actions'] = {
      'put': {
        "href": url_template_dict["form_action"] % {
          "traversed_document_url": site_root.absolute_url() + "/" + traversed_document.getRelativeUrl(),
          "action_id": action_to_call
        },
        "action": form.action,
        "method": form.method,
      }
    }
  # Form traversed_document
  response_dict['_links']['traversed_document'] = {
    "href": default_document_uri_template % {
      "root_url": site_root.absolute_url(),
      "relative_url": traversed_document.getRelativeUrl(),
      "script_id": script.id
    },
    "name": traversed_document.getRelativeUrl(),
    "title": traversed_document.getTitle()
  }

  form_relative_url = getFormRelativeUrl(form)
  response_dict['_links']['form_definition'] = {
#     "href": default_document_uri_template % {
#       "root_url": site_root.absolute_url(),
#       "script_id": script.id,
#       "relative_url": getFormRelativeUrl(form)
#     },
    "href": default_document_uri_template % {
      "relative_url": form_relative_url
    },
    'name': form.id
  }

  # Go through all groups ("left", "bottom", "hidden" etc.) and add fields from
  # them into form.
  for group in form.Form_getGroupTitleAndId():
    # Skipping hidden group could be problematic but see MatrixBox Field above
    if 'hidden' in group['gid']:
      continue
    for field in form.get_fields_in_group(group['goid']):
      if not field.get_value("enabled"):
        continue
      try:
        response_dict[field.id] = renderField(traversed_document, field, form, key_prefix=key_prefix, selection_params=selection_params)
        if field_errors.has_key(field.id):
          response_dict[field.id]["error_text"] = field_errors[field.id].error_text
      except AttributeError:
        # Do not crash if field configuration is wrong.
        pass

  response_dict["form_id"] = {
    "type": "StringField",
    "key": "form_id",
    "default": form.id,
    "editable": 0,
    "css_class": "",
    "hidden": 1,
    "description": "",
    "title": "form_id",
    "required": 1,
  }

  if (form.pt == 'report_view'):
    report_item_list = []
    report_result_list = []
    for field in form.get_fields():
      if field.getRecursiveTemplateField().meta_type == 'ReportBox':
        report_item_list.extend(field.render())
    j = 0
    for report_item in report_item_list:
      report_context = report_item.getObject(portal)
      report_prefix = 'x%s' % j
      j += 1
      report_title = report_item.getTitle()
      # report_class = "report_title_level_%s" % report_item.getLevel()
      report_form = report_item.getFormId()
      report_result = {'_links': {}}
      renderForm(traversed_document, getattr(report_context, report_item.getFormId()),
                 report_result, key_prefix=report_prefix,
                 selection_params=report_item.selection_params)
      report_result_list.append(report_result)

    response_dict['report_section_list'] = report_result_list

# XXX form action update, etc
def renderRawField(field):
  meta_type = field.meta_type

  return {
    "meta_type": field.meta_type
  }


  if meta_type == "MethodField":
    result = {
      "meta_type": field.meta_type
    }
  else:
    result = {
      "meta_type": field.meta_type,
      "_values": field.values,
      # XXX TALES expression is not JSON serializable by default
      # "_tales": field.tales
      "_overrides": field.overrides
    }
  if meta_type == "ProxyField":
    result['_delegated_list'] = field.delegated_list
#     try:
#       result['_delegated_list'].pop('list_method')
#     except KeyError:
#       pass

  # XXX ListMethod is not JSON serialized by default
  try:
    result['_values'].pop('list_method')
  except KeyError:
    pass
  try:
    result['_overrides'].pop('list_method')
  except KeyError:
    pass
  return result


def renderFormDefinition(form, response_dict):
  group_list = []
  for group in form.Form_getGroupTitleAndId():

    if group['gid'].find('hidden') < 0:
      field_list = []

      for field in form.get_fields_in_group(group['goid'], include_disabled=1):
        field_list.append((field.id, renderRawField(field)))

      group_list.append((group['gid'], field_list))
  response_dict["group_list"] = group_list
  response_dict["title"] = Base_translateString(form.getTitle())
  response_dict["pt"] = form.pt
  response_dict["action"] = form.action


mime_type = 'application/hal+json'
portal = context.getPortalObject()
sql_catalog = portal.portal_catalog.getSQLCatalog()

# Calculate the site root to prevent unexpected browsing
is_web_mode = (context.REQUEST.get('current_web_section', None) is not None) or (hasattr(context, 'isWebMode') and context.isWebMode())
# is_web_mode =  traversed_document.isWebMode()
if is_web_mode:
  site_root = context.getWebSectionValue()
  view_action_type = site_root.getLayoutProperty("configuration_view_action_category", default='object_view')
else:
  site_root = portal
  view_action_type = "object_view"

context.Base_prepareCorsResponse(RESPONSE=response)

# Check if traversed_document is the site_root
if relative_url:
  temp_traversed_document = site_root.restrictedTraverse(relative_url, None)
  if (temp_traversed_document is None):
    response.setStatus(404)
    return ""
else:
  temp_traversed_document = context

temp_is_site_root = (temp_traversed_document.getPath() == site_root.getPath())
temp_is_portal = (temp_traversed_document.getPath() == portal.getPath())

def calculateHateoas(is_portal=None, is_site_root=None, traversed_document=None, REQUEST=None,
                     response=None, view=None, mode=None, query=None,
                     select_list=None, limit=None, form=None,
                     relative_url=None, restricted=None, list_method=None,
                     default_param_json=None, form_relative_url=None):

  if relative_url:
    try:
      traversed_document = site_root.restrictedTraverse(str(relative_url))
      view = str(view)
      is_site_root = False
    except:
      raise NotImplementedError(relative_url)
  result_dict = {
    '_debug': mode,
    '_links': {
      "self": {
        # XXX Include query parameters
        # FIXME does not work in case of bulk queries
        "href": traversed_document.Base_getRequestUrl()
      },
      # Always inform about site root
      "site_root": {
        "href": default_document_uri_template % {
          "root_url": site_root.absolute_url(),
          "relative_url": site_root.getRelativeUrl(),
          "script_id": script.id
        },
        "name": site_root.getTitle(),
      },
      # Always inform about portal
      "portal": {
        "href": default_document_uri_template % {
          "root_url": portal.absolute_url(),
          # XXX the portal has an empty getRelativeUrl. Make it still compatible
          # with restrictedTraverse
          "relative_url": portal.getId(),
          "script_id": script.id
        },
        "name": portal.getTitle(),
      }
    }
  }
  
  
  if (restricted == 1) and (portal.portal_membership.isAnonymousUser()):
    login_relative_url = site_root.getLayoutProperty("configuration_login", default="")
    if (login_relative_url):
      response.setHeader(
        'WWW-Authenticate',
        'X-Delegate uri="%s"' % (url_template_dict["login_template"] % {
          "root_url": site_root.absolute_url(),
          "login": login_relative_url
        })
      )
    response.setStatus(401)
    return ""
  
  elif mime_type != traversed_document.Base_handleAcceptHeader([mime_type]):
    response.setStatus(406)
    return ""
  
  
  elif (mode == 'root') or (mode == 'traverse'):
    #################################################
    # Raw document
    #################################################
    if (REQUEST is not None) and (REQUEST.other['method'] != "GET"):
      response.setStatus(405)
      return ""
    # Default properties shared by all ERP5 Document and Site
    action_dict = {}
  #   result_dict['_relative_url'] = traversed_document.getRelativeUrl()
    result_dict['title'] = traversed_document.getTitle()
  
    # Add a link to the portal type if possible
    if not is_portal:
      result_dict['_links']['type'] = {
        "href": default_document_uri_template % {
          "root_url": site_root.absolute_url(),
          "relative_url": portal.portal_types[traversed_document.getPortalType()]\
                            .getRelativeUrl(), 
          "script_id": script.id
        },
        "name": Base_translateString(traversed_document.getPortalType())
      }
      
    # Return info about container
    if not is_portal:
      container = traversed_document.getParentValue()
      if container != portal:
        # Jio does not support fetching the root document for now
        result_dict['_links']['parent'] = {
          "href": default_document_uri_template % {
            "root_url": site_root.absolute_url(),
            "relative_url": container.getRelativeUrl(), 
            "script_id": script.id
          },
          "name": Base_translateString(container.getTitle()),
        }
  
    # XXX Loop on form rendering
    erp5_action_dict = portal.Base_filterDuplicateActions(
      portal.portal_actions.listFilteredActionsFor(traversed_document))
  
    embedded_url = None
    # XXX See ERP5Type.getDefaultViewFor
    for erp5_action_key in erp5_action_dict.keys():
      erp5_action_list = []
      for view_action in erp5_action_dict[erp5_action_key]:
        # Action condition is probably checked in Base_filterDuplicateActions
        erp5_action_list.append({
          'href': '%s' % view_action['url'],
          'name': view_action['id'],
          'icon': view_action['icon'],
          'title': Base_translateString(view_action['title'])
        })
        # Try to embed the form in the result
        if (view == view_action['id']):
          embedded_url = '%s' % view_action['url']

        if erp5_action_key in (view_action_type, "view", "workflow", "object_new_content_action", "object_clone_action", "object_delete_action", "object_report_jio", "object_exchange_jio", "object_fast_input_jio", "object_search_jio", "object_action_jio"):

          erp5_action_list[-1]['href'] = url_template_dict["traverse_generator"] % {
                "root_url": site_root.absolute_url(),
                "script_id": script.id,
                "relative_url": traversed_document.getRelativeUrl().replace("/", "%2F"),
                "view": erp5_action_list[-1]['name']
              }

        if erp5_action_key == 'object_jump':
          if 'Base_jumpToRelatedObject?' in view_action['url']:
            # Fetch the URL arguments
            # XXX Correctly unquote arguments
            argument_dict = dict([x.split('=') for x in view_action['url'].split('?', 1)[1].split("&")])
            jump_portal_type = argument_dict.pop('portal_type', None)
            if (jump_portal_type is not None):
              jump_portal_type = jump_portal_type.replace('+', ' ')
            final_argument_dict = {'portal_type': jump_portal_type}
            jump_related = argument_dict.pop('related', 1)
            if (jump_related):
              jump_related_suffix = ''
            else:
              jump_related_suffix = 'related_'

            jump_uid = portal.restrictedTraverse(argument_dict.pop('jump_from_relative_url', getRealRelativeUrl(traversed_document))).getUid()
            final_argument_dict['default_%s_%suid' % (argument_dict.pop('base_category'), jump_related_suffix)] = jump_uid

            erp5_action_list[-1]['href'] = url_template_dict["jio_search_template"] % {
              "query": make_query({"query": sql_catalog.buildQuery(final_argument_dict).asSearchTextExpression(sql_catalog)})
            }
          else:
            # XXX How to handle all custom jump actions?
            erp5_action_list.pop(-1)

  
      if erp5_action_list:
        if len(erp5_action_list) == 1:
          erp5_action_list = erp5_action_list[0]
          
        if erp5_action_key == view_action_type:
          # Configure view tabs on server level
          result_dict['_links']["view"] = erp5_action_list
          
        # XXX Put a prefix to prevent conflict
        result_dict['_links']["action_" + erp5_action_key] = erp5_action_list
  
  #   for view_action in erp5_action_dict.get('object_view', []):
  #     traversed_document.log(view_action)
  #     # XXX Check the action condition
  # #     if (view is None) or (view != view_action['name']):
  #     object_view_list.append({
  #       'href': '%s' % view_action['url'],
  #       'name': view_action['name']
  #     })
  
  
  #   if (renderer_form is not None):
  #     traversed_document_property_dict, renderer_form_json = traversed_document.Base_renderFormAsSomething(renderer_form)
  #     result_dict['_embedded'] = {
  #       'object_view': renderer_form_json
  #     }
  #     result_dict.update(traversed_document_property_dict)
  
    # XXX XXX XXX XXX
    if (embedded_url is not None):
      # XXX Try to fetch the form in the traversed_document of the document
      # Of course, this code will completely crash in many cases (page template
      # instead of form, unexpected action TALES expression). Happy debugging.
      # renderer_form_relative_url = view_action['url'][len(portal.absolute_url()):]
      form_id = embedded_url.split('?', 1)[0].split("/")[-1]
      # renderer_form = traversed_document.restrictedTraverse(form_id, None)
      # XXX Proxy field are not correctly handled in traversed_document of web site
      renderer_form = getattr(traversed_document, form_id)
  #     traversed_document.log(form_id)
      if (renderer_form is not None):
        embedded_dict = {
          '_links': {
            'self': {
              'href': embedded_url
            }
          }
        }
        # Put all query parameters (?reset:int=1&workflow_action=start_action) in request to mimic usual form display
        query_split = embedded_url.split('?', 1)
        if len(query_split) == 2:
          for query_parameter in query_split[1].split("&"):
            query_key, query_value = query_parameter.split("=")
            REQUEST.set(query_key, query_value)
  
        renderForm(traversed_document, renderer_form, embedded_dict)
        result_dict['_embedded'] = {
          '_view': embedded_dict
          # embedded_action_key: embedded_dict
        }
  #       result_dict['_links']["_view"] = {"href": embedded_url}
  
        # Include properties in document JSON
        # XXX Extract from renderer form?
        """
        for group in renderer_form.Form_getGroupTitleAndId():
          for field in renderer_form.get_fields_in_group(group['goid']):
            field_id = field.id
  #           traversed_document.log(field_id)
            if field_id.startswith('my_'):
              property_name = field_id[len('my_'):]
  #             traversed_document.log(property_name)
              property_value = traversed_document.getProperty(property_name, d=None)
              if (property_value is not None):
                if same_type(property_value, DateTime()):
                  # Serialize DateTime
                  property_value = property_value.rfc822()
                result_dict[property_name] = property_value 
                """
  
    ##############
    # XXX Custom slapos code
    ##############
    if is_site_root:
  
      result_dict['default_view'] = 'view'
      REQUEST.set("X-HATEOAS-CACHE", 1)
  
      # Global action users for the jIO plugin
      # XXX Would be better to not hardcode them but put them as portal type
      # "actions" (search could be on portal_catalog document, traverse on all
      # documents, newContent on all, etc)
  #     result_dict['_links']['object_search'] = {
  #       'href': '%s/ERP5Site_viewSearchForm?portal_skin=Hal' % absolute_url,
  #       'name': 'Global Search'
  #     }
      result_dict['_links']['raw_search'] = {
        "href": url_template_dict["search_template"] % {
          "root_url": site_root.absolute_url(),
          "script_id": script.id
        },
        'name': 'Raw Search',
        'templated': True
      }
      result_dict['_links']['traverse'] = {
        "href": url_template_dict["traverse_template"] % {
          "root_url": site_root.absolute_url(),
          "script_id": script.id
        },
        'name': 'Traverse',
        'templated': True
      }
      action_dict['add'] = {
        "href": url_template_dict["new_content_action"] % {
          "root_url": site_root.absolute_url(),
          "script_id": script.id
        },
        'method': 'POST',
        'name': 'New Content',
      }
      action_dict['bulk'] = {
        "href": url_template_dict["bulk_action"] % {
          "root_url": site_root.absolute_url(),
          "script_id": script.id
        },
        'method': 'POST',
        'name': 'Bulk'
      }
  
      # Handle also other kind of users: instance, computer, master
      person = portal.portal_membership.getAuthenticatedMember().getUserValue()
      if person is not None and portal.portal_membership.checkPermission('View', person):
        result_dict['_links']['me'] = {
          "href": default_document_uri_template % {
            "root_url": site_root.absolute_url(),
            "relative_url": person.getRelativeUrl(), 
            "script_id": script.id
          },
  #         '_relative_url': person.getRelativeUrl()
        }
  
    else:
      traversed_document_portal_type = traversed_document.getPortalType()
      if traversed_document_portal_type == "ERP5 Form":
        renderFormDefinition(traversed_document, result_dict)
        response.setHeader("Cache-Control", "private, max-age=1800")
        response.setHeader("Vary", "Cookie,Authorization,Accept-Encoding")
        response.setHeader("Last-Modified", DateTime().rfc822())
        REQUEST.set("X-HATEOAS-CACHE", 1)
      elif relative_url == 'portal_workflow':
        result_dict['_links']['action_worklist'] = {
          "href": url_template_dict['worklist_template'] % {
            "root_url": site_root.absolute_url(),
            "script_id": script.id
          }
        }
      elif relative_url == 'acl_users':
        logout_relative_url = site_root.getLayoutProperty("configuration_logout", default="")
        if (logout_relative_url):
          result_dict['_links']['logout'] = {
            "href": url_template_dict['logout_template'] % {
              "root_url": site_root.absolute_url(),
              "logout": logout_relative_url,
              "template": True
            }
          }
  
    # Define document action
    if action_dict:
      result_dict['_actions'] = action_dict
  
  
  elif mode == 'search':
    #################################################
    # Portal catalog search
    #
    # Possible call arguments example:
    #  form_relative_url: portal_skins/erp5_web/WebSite_view/listbox
    #  list_method: objectValues                      (Script providing listing)
    #  default_param_json: <base64 encoded JSON>      (Additional search params)
    #  query: <str>                                   (term for fulltext search)
    #  select_list: ['int_index', 'id', 'title', ...] (column names to select)
    #  limit: [15, 16]                                (begin_index, num_records)
    #  local_roles: TODO
    #################################################
    if REQUEST.other['method'] != "GET":
      response.setStatus(405)
      return ""
  
    # hardcoded responses for site and portal objects (which are not Documents!)
    if query == "__root__":
      sql_list = [site_root]
    elif query == "__portal__":
      sql_list = [portal]
    else:
      catalog_kw = {
        "local_roles": local_roles,
        "limit": limit,
        "sort_on": ()  # default is empty tuple
      }
      if default_param_json is not None:
        catalog_kw.update(byteify(json.loads(urlsafe_b64decode(default_param_json))))
      if query:
        catalog_kw["full_text"] = query
      if sort_on is not None:
        if isinstance(sort_on, list):
          catalog_kw['sort_on'] = tuple((byteify(sort_col), byteify(sort_order))
                                         for sort_col, sort_order in map(json.loads, sort_on))
        else:
          sort_col, sort_order = json.loads(sort_on)
          catalog_kw['sort_on'] = ((byteify(sort_col), byteify(sort_order)), )

      if (list_method is None):
        callable_list_method = portal.portal_catalog
      else:
        callable_list_method = getattr(traversed_document, list_method)

      sql_list = callable_list_method(**catalog_kw)

    result_list = []  # returned "content" of the search

    # Cast to list if only one element is provided
    editable_field_dict = {}
    if select_list is None:
      select_list = []
    elif same_type(select_list, ""):
      select_list = [select_list]
  
    if select_list:
      if (form_relative_url is not None):
        listbox_field = portal.restrictedTraverse(form_relative_url)
        listbox_field_id = listbox_field.id
        # XXX Proxy field are not correctly handled in traversed_document of web site
        listbox_form = getattr(traversed_document, listbox_field.aq_parent.id)
        for select in select_list:
          # See Listbox.py getValueList --> getEditableField & getColumnAliasList method
          tmp = select.replace('.', '_')
          if listbox_form.has_field("%s_%s" % (listbox_field_id, tmp), include_disabled=1):
            editable_field_dict[select] = listbox_form.get_field("%s_%s" % (listbox_field_id, tmp), include_disabled=1)
  
    # handle the case when list-scripts are ignoring `limit` - paginate for them
    if limit is not None and isinstance(limit, (tuple, list)):
      start, num_items = map(int, limit)
      if len(sql_list) <= num_items:
        # the limit was most likely taken into account thus we don't need to slice
        start, num_items = 0, len(sql_list)
    else:
      start, num_items = 0, len(sql_list)

    for document_index, sql_document in enumerate(sql_list):
      if document_index < start:
        continue
      if document_index >= start + num_items:
        break

      try:
        document = sql_document.getObject()
      except AttributeError:
        # XXX ERP5 Site is not an ERP5 document
        document = sql_document
      document_uid = sql_document.uid
      document_result = {
        '_links': {
          'self': {
            "href": default_document_uri_template % {
              "root_url": site_root.absolute_url(),
              # XXX ERP5 Site is not an ERP5 document
              "relative_url": getRealRelativeUrl(document) or document.getId(), 
              "script_id": script.id
            },
          },
        }
      }
      if editable_field_dict:
        document_result['listbox_uid:list'] = {
          'key': "%s_uid:list" % listbox_field_id,
          'value': document_uid
        }
      for select in select_list:
        if editable_field_dict.has_key(select):
          REQUEST.set('cell', sql_document)
  
          if ('default' in editable_field_dict[select].tales):
            tmp_value = None
          else:
            tmp_value = getProtectedProperty(document, select)
  
          property_value = renderField(
            traversed_document, editable_field_dict[select], form, tmp_value,
            key='field_%s_%s' % (editable_field_dict[select].id, document_uid))
          REQUEST.other.pop('cell', None)
        else:
          property_value = getProtectedProperty(document, select)
        if property_value is not None:
          if same_type(property_value, DateTime()):
            # Serialize DateTime
            property_value = property_value.rfc822()
          elif isinstance(property_value, datetime.date):
            property_value = formatdate(time.mktime(property_value.timetuple()))
          elif getattr(property_value, 'translate', None) is not None:
            property_value = "%s" % property_value
          document_result[select] = property_value
      result_list.append(document_result)
    result_dict['_embedded'] = {"contents": result_list}
  
    result_dict['_query'] = query
    result_dict['_local_roles'] = local_roles
    result_dict['_limit'] = limit
    result_dict['_select_list'] = select_list
  
  elif mode == 'form':
    #################################################
    # Calculate form value
    #################################################
    if REQUEST.other['method'] != "POST":
      response.setStatus(405)
      return ""
  
    renderForm(traversed_document, form, result_dict)
  
  elif mode == 'newContent':
    #################################################
    # Create new document
    #################################################
    if REQUEST.other['method'] != "POST":
      response.setStatus(405)
      return ""
    portal_type = REQUEST.form["portal_type"]
    parent_relative_url = REQUEST.form["parent_relative_url"]
    # First, try to validate the data on a temp document
    parent = portal.restrictedTraverse(parent_relative_url)
    # module = portal.getDefaultModule(portal_type=portal_type)
    document = parent.newContent(
      portal_type=portal_type
    )
    # http://en.wikipedia.org/wiki/Post/Redirect/Get
    response.setStatus(201)
    response.setHeader("X-Location",
      default_document_uri_template % {
        "root_url": site_root.absolute_url(),
        "relative_url": document.getRelativeUrl(),
        "script_id": script.id
      })
    return ''
  
  elif mode == 'bulk':
    #################################################
    # Return multiple documents in one request
    #################################################
    if REQUEST.other['method'] != "POST":
      response.setStatus(405)
      return ""
    result_dict["result_list"] = [calculateHateoas(mode="traverse", **x) for x in byteify(json.loads(bulk_list))]
  
  elif mode == 'worklist':
    #################################################
    # Return all worklist jio urls
    #################################################
    if REQUEST.other['method'] != "GET":
      response.setStatus(405)
      return ""
    action_list = portal.portal_workflow.WorkflowTool_listActionParameterList()
    work_list = []
    for action in action_list:
      query = sql_catalog.buildQuery(action['query'])\
                         .asSearchTextExpression(sql_catalog)

      if (action['local_roles']):
        # Hack to consider local_roles as a valid catalog parameter
        role_query = sql_catalog.buildQuery({'simulation_state': action['local_roles']})\
                                .asSearchTextExpression(sql_catalog)

        query += ' AND %s' % role_query.replace('simulation_state', 'local_roles')
      worklist_dict = {
        'href': url_template_dict["jio_search_template"] % {
          "query": make_query({"query": query})
        },
        'name': Base_translateString(re.sub(r' \(\d+\)$', '', action['name'])),
        'count': action['count']
      }

      portal_type_list = action['query'].get('portal_type', None)
      if (portal_type_list):
        worklist_module_id = None
        if same_type(portal_type_list, ''):
          portal_type_list = [portal_type_list]

        for portal_type in portal_type_list:
          if (worklist_module_id is None):
            worklist_module_id = portal.getDefaultModuleId(portal_type, default=None, only_visible=True)
          elif (worklist_module_id != portal.getDefaultModuleId(portal_type, default=None, only_visible=True)):
            worklist_module_id = None
          if worklist_module_id is None:
            break

        if (worklist_module_id is not None):
          worklist_dict['module'] = default_document_uri_template % {
            "relative_url": worklist_module_id
          }
      work_list.append(worklist_dict)

    result_dict["worklist"] = work_list

  else:
    raise NotImplementedError("Unsupported mode %s" % mode)
  
  return result_dict

response.setHeader('Content-Type', mime_type)
hateoas = calculateHateoas(is_portal=temp_is_portal, is_site_root=temp_is_site_root,
                           traversed_document=temp_traversed_document,
                           relative_url=relative_url,
                           REQUEST=REQUEST, response=response, view=view, mode=mode,
                           query=query, select_list=select_list, limit=limit, form=form,
                           restricted=restricted, list_method=list_method,
                           default_param_json=default_param_json,
                           form_relative_url=form_relative_url)
if hateoas == "":
  return hateoas
else:
  return json.dumps(hateoas, indent=2)
