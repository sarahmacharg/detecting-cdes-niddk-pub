import json

# TODO: Some information about CDE structure TBD or may be useful to parse in the future. valueDomain: unclear what
#  "identifiers" or "ids" holds. IDs: id name potentially interesting? Some are just numbers, some are coded. Source
#  could encode type of CDE/genre --> speed up search for CDE matches? So might classification? Could combine with
#  UMLS Metathesaurus information on hierarchical relationships between CUIS?


def parse_cde_json(cde_filename):
    """
    :param cde_filename: string. String path to CDE JSON file
    :return: dictionary.
    {'classification': [list of strings of words in the classification tree],
    descriptive text': [str(definition/designation in cde JSON), ...],
    'values': {
        'type': string(CDE type as listed in datatype field),
        'description': string(value name, definition if available),
        'parameters': {dictionary of parameters as relevant to datatype, e.g. min, max, precision for number},
        'text': [Values listed under 'text', unclear what this field means, may be empty (?)],
        values': {
            'encoding': [list of strings of value encodings (e.g. '1' or 'YES'],
            'text': [list of strings of decoded value names and meanings (e.g. 'Grade 1 -- A little bit' or
                    'Yes - The affirmative answer')]
                }
        },
    'ids': {
        'sources': [list of strings of CDE sources, e.g. 'NINDS' or 'PHENX'],
        'ids': [list of strings of ids associated with the CDE in the source (?)]
        }
    }
    """
    cde_file = open(cde_filename, 'r')
    cde_obj = json.loads(cde_file.read())
    # Categories w relevant content: 'valueDomain', 'classification', 'definitions', 'designations', 'ids', 'properties'
    cde_content = parse_cde_obj(cde_obj)
    # Classification contains related fields (potentially useful), but not much information about what the CDE measures
    return cde_content


def parse_cde_obj(cde_obj):
    """
    :param cde_obj: CDE JSON object
    :return: dictionary.
    {'classification': [list of strings of words in the classification tree],
    descriptive text': [str(definition/designation in cde JSON), ...],
    'values': {
        'type': string(CDE type as listed in datatype field),
        'description': string(value name, definition if available),
        'parameters': {dictionary of parameters as relevant to datatype, e.g. min, max, precision for number},
        'text': [Values listed under 'text', unclear what this field means, may be empty (?)],
        values': {
            'encoding': [list of strings of value encodings (e.g. '1' or 'YES'],
            'text': [list of strings of decoded value names and meanings (e.g. 'Grade 1 -- A little bit' or
                    'Yes - The affirmative answer')]
                }
        },
    'ids': {
        'sources': [list of strings of CDE sources, e.g. 'NINDS' or 'PHENX'],
        'ids': [list of strings of ids associated with the CDE in the source (?)]
        }
    }
    """
    # Categories w relevant content: 'valueDomain', 'classification', 'definitions', 'designations', 'ids', 'properties'
    cde_content = {'classification': parse_cde_classification(cde_obj),
                   'descriptive text': parse_cde_question(cde_obj),
                   'values': parse_cde_values(cde_obj), 'ids': parse_ids(cde_obj)}
    # Classification contains related fields (potentially useful), but not much information about what the CDE measures
    return cde_content


def parse_cde_classification(cde_obj):
    """
    Wrapper function for parse_cde_classification_rec
    :param cde_obj: CDE JSON object
    :return: list(string). List of strings of words in the classification tree
    """
    classification_tree_list = cde_obj['classification']
    classifiers_list = []
    parse_cde_classification_tree_rec(classification_tree_list, classifiers_list)
    return classifiers_list


def parse_cde_classification_tree_rec(classification_tree_list, classifiers_list):
    """
    Recursively traverses classification tree portion of JSON to pull out all the words at each level.
    :param classification_tree_list: list in JSON object that CDE repository uses to represent the classification tree
    (many nested dictionaries and lists, see pretty cdes in misc/ for more context).
    :param classifiers_list: list(string). List of currently found words in the classification tree.
    :return: list(string). List of strings of words found in the classification tree
    """
    for dictionary in classification_tree_list:
        for key in dictionary.keys():
            value = dictionary[key]
            if key == 'name':
                if value == 'Classification':  # Information under 'classification' NOT informative, don't explore
                    break
                elif value != 'Domain':  # The word 'domain' itself contains no info about nature of CDE
                    classifiers_list.append(dictionary[key])
            elif key == 'elements':
                parse_cde_classification_tree_rec(value, classifiers_list)  # Recurse to explore classification tree
    return None


def parse_cde_question(cde_obj):
    """
    :param cde_obj: CDE JSON object
    :return: list(string). List of strings of definitions or designations associated with the CDE (descriptions of what
    the CDE is/measures).
    """
    question_content = []
    for definition_obj in cde_obj['definitions']:
        question_content.append(definition_obj['definition'])
    for designation_obj in cde_obj['designations']:
        question_content.append(designation_obj['designation'])
    return question_content


def parse_cde_values(cde_obj):
    """
    :param cde_obj: CDE JSON Object
    :return: dictionary. Dictionary containing all the information the CDE JSON contains about the permissible values:
    {'type': string(CDE type as listed in datatype field),
    'description': string(value name, definition if available),
    'parameters': {dictionary of parameters as relevant to datatype, e.g. min, max, precision for number},
    'text': [Values listed under 'text', unclear what this field means, may be empty (?)],
    values': {
        'encoding': [list of strings of value encodings (e.g. '1' or 'YES'],
        'text': [list of strings of decoded value names and meanings (e.g. 'Grade 1 -- A little bit' or
                'Yes - The affirmative answer')]
            }
    }
    """
    value_info = {'type': '', 'description': '', 'parameters': {}, 'text': [], 'values': {'encoding': [], 'text': []}}
    value_domain = cde_obj['valueDomain']
    for key in value_domain.keys():
        if str(key) == 'datatype':
            value_info['type'] = value_domain[key]
        elif 'datatype' in str(key):
            datatype_info = value_domain[key]
            for parameter in datatype_info.keys():
                value_info['parameters'][str(parameter)] = datatype_info[parameter]
        elif str(key) == 'name':
            if 'definition' in value_domain.keys():
                value_info['description'] = value_domain['name'] + ' -- ' + value_domain['definition']
            else:
                value_info['description'] = value_domain['name']
        elif str(key) == 'uom':
            value_info['parameters'][str(key)] = value_domain[key]
        elif str(key) == 'permissibleValues':
            permissible_value_list = value_domain[key]
            for value_obj in permissible_value_list:
                value_info['values']['encoding'].append(value_obj['permissibleValue'])
                if 'valueMeaningName' in value_obj.keys() and 'valueMeaningDefinition' in value_obj.keys():
                    value_info['values']['text'].append(value_obj['valueMeaningName'] + ' -- ' + value_obj['valueMeaningDefinition'])
                elif 'valueMeaningName' in value_obj.keys():
                    value_info['values']['text'].append(value_obj['valueMeaningName'])
                elif 'valueMeaningDefinition' in value_obj.keys():
                    value_info['values']['text'].append(value_obj['valueMeaningDefinition'])
        if str(key) == 'definition' and 'name' not in value_domain.keys():
            value_info['description'] = value_domain['definition']
    return value_info


def parse_ids(cde_obj):
    """
    :param cde_obj: CDE JSON object
    :return: dict. {'sources': [list of 'sources' for CDE], 'ids': [list of 'ids' for CDE]}
    """
    id_info = {'sources': [], 'ids': []}
    id_list = cde_obj['ids']
    for id_obj in id_list:
        id_info['sources'].append(id_obj['source'])
        id_info['ids'].append(id_obj['id'])
    return id_info

