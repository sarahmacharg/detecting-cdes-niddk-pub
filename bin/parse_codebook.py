import pandas as pd
from pint import UnitRegistry
import re
import os

# Read in constant custom stopwords list
with open(os.path.join('const', 'custom_stopwords.txt')) as f:
    CUSTOM_STOPWORDS = [line.strip() for line in f]


def cdb_to_dataframe(cdb_filename):
    """
    :param cdb_filename: string. String path to codebook .txt file
    :return: pandas DataFrame. Dataframe holding the same information as the codebook. Generally of the form:
    Index: 'Variable'  || 'Column'        'Len'           'Format'     'Question'     'Description'    'Code'
    --------------------------------------------------------------------------------------------------------------------
    Variable ID        || Column number   Length of       Format ID     Form section    Free text       Concatenated
                          the variable    the variable                  and question    description     value codes and
                          appears in                                    where           of variable     value
                                                                        question asked/                 descriptions
                                                                        variable measured
    """
    columns, values = cdb_to_lists(cdb_filename)
    variable_df = pd.DataFrame(data=values, columns=columns)
    variable_df = variable_df.set_index('Variable')
    return variable_df


def cdb_to_lists(cdb_filename):
    """
    :param cdb_filename: string. String path to codebook .txt file
    :return: (list(str), list(str)). Tuple of list columns and list values. List columns lists the column headings from the
    codebook, list values contains lists of the values in the codebook for each row. Empty cells are denoted with the
    empty string
    """
    with open(cdb_filename, 'r') as file:
        var_data = []
        values = []
        for (i, line) in enumerate(file):
            if 'Column' in line:
                columns = line.split()
                table_start = i
                break
    with open(cdb_filename, 'r') as file:
        for (i, line) in enumerate(file):
            if i == table_start + 1:
                section_lengths, description_start, code_start = get_start_indices(line, columns)
            elif i > table_start + 1:
                encoded_data = line[:description_start]  # Column, Len, Format, Variable name, Section/Question
                if len(encoded_data.split()) != 0:  # When line is start of a new variable
                    if var_data:  # Store information from the previous variable
                        values.append(var_data)
                    var_data = initialize_var_data(line, columns, section_lengths, description_start,
                                                   code_start, encoded_data)
                else:  # When line is a continuation of variable info
                    var_data = extend_var_data(var_data, line, columns, description_start, code_start)
    values.append(var_data)
    return columns, values


def get_start_indices(line, columns):
    """
    :param line: string. The dashed line that separates codebook column names from codebook content
    :param columns: list(string). List of string column names extracted from the column headings of the codebook
    :return: (list(int), int, int). Tuple containing list of the widths of each section in the codebook (in # of
    characters), integer index where 'Description' column begins, and integer index where 'Code' column begins.

    """
    description_start = 0
    sections = line.split()
    for j, section in enumerate(sections):
        if j < columns.index('Description'):
            description_start += len(section) + 1
    code_start = description_start + len(sections[columns.index('Description')]) + 1
    section_lengths = []
    for section in sections:
        section_lengths.append(len(section))
    return section_lengths, description_start, code_start


def initialize_var_data(line, columns, section_lengths, description_start, code_start, encoded_data):
    """
    :param line: string. String of the first line of a row in the codebook (one variable's information)
    :param columns: list(string). List of the string column names.
    :param section_lengths: list(int). List of the widths of each section in the codebook (in # of
    characters)
    :param description_start: int. Integer index where 'Description' column begins
    :param code_start: int. Integer index where 'Code' column begins.
    :param encoded_data: string. The portion of the line string spanning the 'Description' and 'Code' columns.
    :return: list(str). List of strings, where each string is the first line of text for each column (in the codebooks,
    descriptions often span multiple lines, so this function initiates the strings).
    """
    var_data = encoded_data.split()  # Break up encoded values into a list
    if len(var_data) != columns.index('Description'):  # If no Section/Question indicated, use ''
        var_data = []
        last = 0
        for i, section_length in enumerate(section_lengths[:columns.index('Description')]):
            this_section = encoded_data[last:last + section_length]
            if len(this_section.split()) == 0:
                var_data.append('')
            else:
                var_data.append('fill')
            last = last + section_length + 1
        start = 0
        for section in encoded_data.split():
            next_spot = var_data.index('fill', start)
            var_data[next_spot] = section
            start = next_spot + 1
    var_data.append(line[description_start:code_start].strip())  # Append the first line of description
    var_data.append(line[code_start:].strip())  # Append the first line of value encoding info
    return var_data


def extend_var_data(var_data, line, columns, description_start, code_start):
    """
    :param var_data: list(str). List of strings, where each string is text for each column (in the codebooks,
    descriptions often span multiple lines, so strings are built up iteratively).
    :param line: string. String of a line of the codebook that isn't the first line of a variable's row.
    :param columns: list(string). List of the string column names.
    :param description_start: int. Integer index where 'Description' column begins
    :param code_start: int. Integer index where 'Code' column begins.
    :return: list(str). List of strings, where each string is the text for each column for a given variable, and the
    text from the line passed into this function has been split and each part appended to the appropriate string.
    """
    extra_description = line[description_start:code_start].strip()  # Get additional description text
    extra_code = line[code_start:].strip()  # Get additional value encoding text
    if len(extra_description) != 0:  # If additional description text, concatenate w/ description
        var_data[columns.index('Description')] = var_data[columns.index('Description')] + ' ' \
                                                 + extra_description
    if len(extra_code) != 0:  # If additional value encoding info, concatenate w/ encoding info
        encodings = re.search(r"[^<>]=", extra_code)
        if encodings or extra_code == '.' or is_decimal(extra_code):
            var_data[columns.index('Code')] = var_data[columns.index('Code')] + ';; ' + extra_code
        else:
            if var_data[columns.index('Code')][len(var_data[columns.index('Code')])-1] == '.':
                var_data[columns.index('Code')] = var_data[columns.index('Code')] + ';; ' + extra_code
            else:
                var_data[columns.index('Code')] = var_data[columns.index('Code')] + ' ' + extra_code
    return var_data


def parse_codebook_values(codebook_elements_df, display, uncertain_uoms, debug):
    """
    :param codebook_elements_df: pandas DataFrame. Dataframe holding the same information as the codebook. Generally:
    Index: 'Variable'  || 'Column'        'Len'           'Format'     'Question'     'Description'    'Code'
    --------------------------------------------------------------------------------------------------------------------
    Variable ID        || Column number   Length of       Format ID     Form section    Free text       Concatenated
                          the variable    the variable                  and question    description     value codes and
                          appears in                                    where           of variable     value
                                                                        question asked/                 descriptions
                                                                        variable measured
    :param display: bool. True => prints results.
    :param uncertain_uoms: bool. True => Checks for units of measure in variable/value descriptions
    :param debug: bool. True => prints debugging information.
    :return: dictionary:
        {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
    ----------If value list----------
        'value_list_vals': {str(value code): value description, ...},
    ----------If text----------
        'val': str(description of text field)
    ---------------------------
        },
        ...
    }
    """
    codebook_values = {}
    for ind in codebook_elements_df.index:
        value_set_string = codebook_elements_df.loc[ind, 'Code']
        if debug:
            print('var: ', ind, 'encoding: ', value_set_string)
        codebook_values[ind] = {}
        codebook_values[ind]['len'] = codebook_elements_df.loc[ind, 'Len']
        if '.;; .;;' in value_set_string and codebook_elements_df.loc[ind, 'Format'] != '$':  # Non-character list with "..." in it
            numeric = True
        else:
            numeric = False
        if numeric:
            codebook_values[ind]['type'] = 'Number'  # Set type to Number
            parse_ranged_list(value_set_string, codebook_values, ind)  # Get values in this ranged ("...") list
            if type(codebook_values[ind]['min']) == dict:  # If values were encoded (X= X_Meaning)
                min_code = list(codebook_values[ind]['min'].keys())[0]
                min_val = codebook_values[ind]['min'][min_code]
                if min_val[:len(min_code)] == min_code:
                    codebook_values[ind]['value_list'] = False  # If the code and meaning are the same (but maybe with units), not a value list
                else:
                    codebook_values[ind]['value_list'] = True  # If the code and meaning not the same, not a value list
            else:
                codebook_values[ind]['value_list'] = False  # If values not encoded, not a value list
        else:  # If type not yet determined to be Number
            listed = ';; ' in value_set_string  # If it has ";; " value separator, it's a list of values
            if listed:
                if '.;; .;;' in value_set_string:  # If "..." in string but it wasn't numeric
                    if '/' in value_set_string:
                        codebook_values[ind]['type'] = 'Date'  # Values with slashes in them are dates - this is CKiD specific and perhaps not fully accurate
                        codebook_values[ind]['value_list'] = False  # Range of dates => not a value list
                    else:
                        codebook_values[ind]['type'] = 'Text'  # Otherwise, it's a value list with value type 'Text'
                        codebook_values[ind]['value_list'] = True
                    parse_ranged_list(value_set_string, codebook_values, ind)  # Get max and min values, supplemental info
                else:  # If not a ranged list (no "...")
                    codebook_values[ind]['value_list'] = True  # It's a value list
                    values = value_set_string.split(';; ')  # Split up values by value separator
                    if '= ' in values[0]:
                        value_encoded = values[0].split('= ')[0]  # If encoded value, split value into code and meaning
                    else:
                        value_encoded = values[0]
                    if is_decimal(value_encoded):  # If the value code is a number, value list type is number
                        codebook_values[ind]['type'] = 'Number'
                    else:  # Otherwise, value list type is text
                        codebook_values[ind]['type'] = 'Text'
                    last = None
                    codebook_values[ind]['value_list_vals'] = {}
                    for value in values:  # Start appending code/meaning key-value pairs to dictionary
                        last, codebook_values = parse_encoded_value(value, last, codebook_values, ind, 'valuelist')
            else:  # If not numeric and not listed (just one value)
                codebook_values[ind]['value_list'] = False  # Not a value list
                codebook_values[ind]['type'] = 'Text'  # Type is text
                codebook_values[ind]['val'] = value_set_string  # Set 'val' to be the string describing the text
    if uncertain_uoms:  # Parse descriptions for units of measurement if indicated that you should
        add_potential_uoms(codebook_elements_df, codebook_values)
    if display:
        print(codebook_values)
    return codebook_values


def parse_ranged_list(value_set_string, codebook_values, ind):
    """
    :param value_set_string: string. String of all encoded values and their decodings (if applicable) included in the
    codebook, separated by ';; '
    :param codebook_values: dictionary:
        {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        },
        ...
    }
    :param ind: string. Variable ID of variable being processed (index of that row of the codebook dataframe).
    :return: dictionary:
        {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
        },
        ...
    }
    """
    values = value_set_string.split(';; ')  # Split values by value separator ";; "
    min_info = values[0]  # First value
    first_period = values.index('.')  # Find where ranged list starts in the string
    max_info = values[first_period + 2]  # Max of the range (codebook encodes ranges as "min, ., ., max"
    if '= ' in min_info:  # If values are encoded
        min_value_encoded, min_value_decoded = min_info.split('= ')[0], min_info.split('= ')[1]  # Split into code and meaning
        max_value_encoded, max_value_decoded = max_info.split('= ')[0], max_info.split('= ')[1]
    else:  # Otherwise set code and meaning variables to be the same thing
        min_value_encoded = min_value_decoded = min_info
        max_value_encoded = max_value_decoded = max_info
    unit_of_measure = None
    if len(min_value_decoded.split()) > 1 and is_decimal(min_value_decoded.split()[0]):  # If the value meaning has a space and the first word is a decimal
        unit_of_measure = min_value_decoded.split()[1]  # Then the second word is a unit of measurement (e.g. "50 years")
    if is_decimal(min_value_decoded):  # If the value meaning is a number too (e.g. 0.00 = 0.00)
        codebook_values[ind]['value_list'] = False  # Not a value list
        codebook_values[ind]['min'] = min_value_encoded  # Set 'min' value to the min value
        codebook_values[ind]['max'] = max_value_encoded  # Set 'max' value to the max value
    elif min_value_encoded == min_value_decoded:  # If the encodings and decodings are the same, no need for dictionary
        codebook_values[ind]['min'] = min_value_encoded  # Set 'min' value to the min value
        codebook_values[ind]['max'] = max_value_encoded  # Set 'max' value to the max value
    else:  # If the encoding and decoding (code and meaning aren't the same), use a dictionary to indicate min and max values
        codebook_values[ind]['min'] = {min_value_encoded: min_value_decoded}
        codebook_values[ind]['max'] = {max_value_encoded: max_value_decoded}
    if unit_of_measure:  # If there was a unit of measure detected in the values because of formatting (e.g. with "50 years"
        if 'potential_uoms' in codebook_values[ind].keys():  # Add it to the list associated with key 'potential_uoms'
            codebook_values[ind]['potential_uoms'].append(unit_of_measure)
        else:  # Make a list if there isn't one
            codebook_values[ind]['potential_uoms'] = [unit_of_measure]
    if len(values) > first_period + 3:  # If there are values beyond the range, e.g. "min, ., ., max, other, other
        parse_ranged_list_exceptions(value_set_string, codebook_values, ind, first_period + 3)  # Generate supplemental value dictionary
    return codebook_values


def parse_ranged_list_exceptions(value_set_string, codebook_values, ind, supp_start):
    """
    Adds 'supplemental info' key and dictionary value to the growing dictionary in cases where there is a ranged list
    but also some supplemental value (e.g. '9 or blank: missing')
    :param value_set_string: string. String of all encoded values and their decodings (if applicable) included in the
    codebook, separated by ';; '
    :param codebook_values:
    {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
        ...
    }
    :param ind: string. Variable ID of variable being processed (index of that row of the codebook dataframe).
    :param supp_start: int. Index of the first 'supplemental value' in the list of permissible values.
    :return: dictionary:
    {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
        },
        ...
    }
    """
    values = value_set_string.split(';; ')  # Split values by value separator ";; "
    supplemental_info = values[supp_start:]  # Look only at values after the max value in the range list "min, ., ., max, other, other, ..."
    codebook_values[ind]['supplemental'] = {}  # Initiate supplemental info dictionary
    last = None
    for value in supplemental_info:  # Decode and add values to supplemental dictionary
        last, codebook_values = parse_encoded_value(value, last, codebook_values, ind, 'numeric')
    return codebook_values


def parse_encoded_value(value, last, codebook_values, ind, type_string):
    """
    For a given value encoding and explanation in the codebook, this function parses the value and adds it as a
    key-value pair to the dictionary codebook_values[VARIABLE_ID]['value_list_vals'] when type_string = 'valuelist' or
    to the dictionary codebook_values[VARIABLE_ID]['supplemental'] when type_string = 'numeric'.
    :param value:
    :param last: string of previous value CODE or tuple of strings of previous value CODES. For example, if the last
    value parsed were '8=No', then last would be '8'. If the last value parsed were '9 or Blank = Missing', then last
    would be ('9', 'Blank').
    :param codebook_values:
    {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
    ----------
        'value_list_vals': {empty dict or str(value code): value description, ...},
        },
        ...
    }
    :param ind: string. Variable ID of variable being processed (index of that row of the codebook dataframe).
    :param type_string: string 'numeric' or string 'valuelist'.
    :return: tuple(string, dictionary). String: the string or tuple(strings) of the value code(s) just parsed. Dict:
    {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
    ----------
        'value_list_vals': {str(value code): value description, ...},
        },
        ...
    }

    """
    if '= ' in value:  # If the value string has '= ', aka '1= Great'
        value_encoded, value_decoded = value.split('= ')[0], value.split('= ')[1]  # Split into code and meaning
        if 'or' in value_encoded:  # If multiple codes attached to same meaning, e.g. '9 or Blank = Missing'
            value1_encoded, value2_encoded = value_encoded.split(' or ')[0], value_encoded.split(' or ')[1]  # Get both codes
            if type_string == 'numeric':  # If we're adding supplemental information that came after a numerical range
                codebook_values[ind]['supplemental'][value1_encoded] = value_decoded  # Add value pair code1-meaning to supplemental dict
                codebook_values[ind]['supplemental'][value2_encoded] = value_decoded  # Add value pair code2-meaning to supplemental dict
            else:  # If we're decoding a standard value list
                codebook_values[ind]['value_list_vals'][value1_encoded] = value_decoded  # Add value pair code1-meaning to value list value dict
                codebook_values[ind]['value_list_vals'][value2_encoded] = value_decoded  # Add value pair code2-meaning to value list value dict
            last = value1_encoded, value2_encoded
        else:  # If simple one code to one meaning mapping
            if type_string == 'numeric':  # If we're adding supplemental information that came after a numerical range
                codebook_values[ind]['supplemental'][value_encoded] = value_decoded  # Add value pair code-meaning to supplemental dict
            else:  # If we're decoding a standard value list
                codebook_values[ind]['value_list_vals'][value_encoded] = value_decoded  # Add value pair code-meaning to value list value dict
            last = value_encoded
    else:   # If '= ' not in the value string, we are dealing with a multiple-line encoded value, so we need to append
            # this line to the strings from the previous lines
        value_decoded = value  # Just get the value string
        if last:
            if len(last) == 1:  # If the last decoded value had a simple one code to one meaning mapping
                if type_string == 'numeric':
                    codebook_values[ind]['supplemental'][last] += value_decoded  # Append this line to the previous meaning
                else:
                    codebook_values[ind]['value_list_vals'][last] += value_decoded  # Append this line to the previous meaning
            elif len(last) == 2:
                if type_string == 'numeric':
                    codebook_values[ind]['supplemental'][last[0]] += value_decoded  # Append this line to both of the previous code-meaning pairs
                    codebook_values[ind]['supplemental'][last[1]] += value_decoded
                else:
                    codebook_values[ind]['value_list_vals'][last[0]] += value_decoded  # Append this line to both of the previous code-meaning pairs
                    codebook_values[ind]['value_list_vals'][last[1]] += value_decoded
    return last, codebook_values


def add_potential_uoms(codebook_elements_df, codebook_values):
    """
    Adds list of potential units of measurement for every variable in the codebook dataframe
    :param codebook_elements_df: pandas DataFrame. Dataframe holding the same information as the codebook. Generally:
    'Column'        'Len'           'Format'    'Variable'      'Question'     'Description'    'Code'
    --------------------------------------------------------------------------------------------------------------------
    Column number   Length of       Format ID   Variable ID     Form section    Free text       Concatenated value codes
    the variable    the variable                                and question    description     and value descriptions
    appears in                                                  where           of variable
                                                                question asked/
                                                                variable measured
    :param codebook_values: dictionary:
        {VARIABLE_ID: {
        'len': length of variable as listed in the codebook,
        'type': 'Number', 'Text', or 'Date' (if '/' in value),
        'value_list': True or False,
        'potential_uoms': [str(detected unit 1), ...],
    ----------If numbers or long form ('...' form) value list----------
        'min': str(minimum allowable value) if not encoded, otherwise {str(min value code): str(min value description)},
        'max': str(maximum allowable value) if not encoded, otherwise {str(max value code): str(max value description)},
    ----------If numbers and there are additional specifications to show blank/missing data----------
        'supplemental': {str(value code): str(value description)},
    ----------If value list----------
        'value_list_vals': {str(value code): value description, ...},
    ----------If text----------
        'val': str(description of text field)
    ---------------------------
        },
        ...
    }
    :return: Same dictionary as param codebook_values, but with updated key 'potential_uoms' that contains a list of
    potential units of measure (string) identified by pint (key may exist before running this function, in which case
    the list is extended).
    """
    ureg = UnitRegistry()
    chunks = generate_meas_chunks(codebook_elements_df)  # Get list of sentence strings "{Variable description} was {decoded value}"
    for i, ind in enumerate(codebook_elements_df.index):
        chunk = chunks[i]
        if type(chunk) != str:
            chunk = chunk.iloc[0]
        uoms = []
        Q_ = ureg.Quantity
        subs = re.split(',|_|-|!|\.|\(|\)| ', chunk)
        for sub in subs:  # Search by word
            if not sub.lower() in CUSTOM_STOPWORDS:  # Don't check stopwords for uoms, helps to filter out weird uoms that pint detects
                try:
                    quantity = (Q_(sub))
                    if str(quantity.units) != 'dimensionless' and str(quantity.units) not in uoms:
                        uoms.append(str(quantity.units))  # If a new uom detected, append to the list of uoms
                except:
                    pass
        if len(uoms) > 0:
            codebook_values[ind]['potential_uoms'] = uoms
    return codebook_values


def generate_meas_chunks(codebook_elements_df):
    """
    :param codebook_elements_df: pandas DataFrame. Dataframe holding the same information as the codebook. Generally:
    Index: 'Variable'  || 'Column'        'Len'           'Format'     'Question'     'Description'    'Code'
    --------------------------------------------------------------------------------------------------------------------
    Variable ID        || Column number   Length of       Format ID     Form section    Free text       Concatenated
                          the variable    the variable                  and question    description     value codes and
                          appears in                                    where           of variable     value
                                                                        question asked/                 descriptions
                                                                        variable measured
    :return: list(string). List of strings reading '{variable description} was {first decoded permissible value}',
            one string per variable
    """
    chunks = []
    for ind in codebook_elements_df.index:
        chunk = ''
        variable_description = str(codebook_elements_df.loc[ind, 'Description'])  # Get variable description
        chunk += variable_description + ' was '
        value = str(codebook_elements_df.loc[ind, 'Code'])
        first_value_end = value.find(';;')
        if first_value_end != -1:  # IF a list of values
            first_value = codebook_elements_df.loc[ind, 'Code'][:first_value_end]  # Get first value
        else:  # Otherwise
            first_value = value  # Just get the value
        if '=' in first_value:
            content_start = first_value.find('= ')
            content = first_value[content_start + 1:]  # If encoded value, get the meaning, not the code
        else:
            content = first_value
        chunk += content  # Chunk now = "{Variable description} was {value meaning for first of permissible values}"
        chunks.append(chunk)  # Append to list of chunks
    return chunks


def is_decimal(s):
    """
    :param s: string
    :return: True if string represents a valid decimal number, else False.
    """
    try:
        float(s)
    except ValueError:
        return False
    else:
        return True
