import inspect
import json
import sys
import yaml
import os
import re
from parinx import parser
from package_creator import clean_python_code

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.abspath(SCRIPT_DIR + '/..')
sys.path.append(CONTENT_DIR + '/Tests/demistomock')

import demistomock  # noqa: E402

# PrivateFuncs are functions to ignore when running the script
jsPrivateFuncs = ["dqQueryBuilder", "toArray", "indent", "formatTableValuesRecursive", "string_to_array",
                  "array_to_hex_string", "SHA256_init", "SHA256_write", "SHA256_finalize", "SHA256_hash",
                  "HMAC_SHA256_init", "HMAC_SHA256_write", "HMAC_SHA256_finalize", "HMAC_SHA256_MAC"]

pyPrivateFuncs = ["raiseTable", "zoomField", "epochToTimestamp", "formatTimeColumns", "strip_tag", "elem_to_internal",
                  "internal_to_elem", "json2elem", "elem2json", "json2xml", "OrderedDict", "datetime", "timedelta",
                  "createContextSingle", "IntegrationLogger", "tblToMd", "DemistoException", "BaseClient",
                  "BaseHTTPClient", "DemistoHandler", "DebugLogger"]

pyIrregularFuncs = {"LOG": {"argList": ["message"]}}

jsAutomationOnly = ["fileNameFromEntry", "closeInvestigation", "setSeverity", "setIncident", "createNewIncident",
                    "setPlaybookAccordingToType", "setOwner", "taskAssign", "setTaskDueDate", "setPlaybook", "addTask",
                    "getCSVListAsArray", "getJSONListAsObject"]

markdownDescFuncs = ["createEntry"]


def readJsonFile(filepath):
    with open(filepath, 'r') as f:
        out = json.load(f)
        return out


def readYmlFile(filepath):
    with open(filepath, 'r') as f:
        out = yaml.safe_load(f)
        return out


def reformatPythonOutput(output, origin, language):
    res = []
    isError = False
    for a in output:
        if "deprecated" in a["description"]:
            continue

        if a.get("description", "") == "":
            print("Description is missing for Python function", a["name"])
            isError = True

        # format arguments
        z = []
        argList = a.get("argList", [])
        argDetails = a.get("arguments", {})
        for argName in argList:
            argInfo = argDetails.get(argName, None)
            if argInfo is not None:
                argInfo["name"] = argName
                argInfo["type"] = argInfo["type_name"]
                if argInfo.get("description", "") == "":
                    isError = True
                    print("Missing description for argument", argName, "in python function", a["name"])
                del argInfo["type_name"]
                z.append(argInfo)

        a["arguments"] = z
        a["return_value"] = a["return"]
        a["return_value"]["type"] = a["return_value"]["type_name"]
        if a["name"] in markdownDescFuncs:
            a["markdown"] = True
        a["language"] = language
        a["origin"] = origin

        del a["argList"]
        del a["return"]
        del a["return_value"]["type_name"]
        res.append(a)

    return res, isError


def createJsDocumentation(path, origin, language):
    isError = False
    commonServerJs = readJsonFile(path)
    x = []
    for a in commonServerJs:
        if (a.get("deprecated", None) is not None) or a.get("name", "") in jsPrivateFuncs:
            continue

        y = {}
        y["name"] = a.get("name", "")
        if y["name"] == "":
            print("Error extracting function name for JS fucntion with the following data:\n", a)
            isError = True
        y["description"] = a.get("description", "")
        if y["description"] == "":
            print("Description is missing for JS function", y["name"])
            isError = True

        for arg in a.get("params", []):
            arg["type"] = " or ".join(arg.get("type", {}).get("names", []))
            arg["required"] = True
            if arg.get("optional"):
                arg["required"] = False
                del arg["optional"]
            if arg.get("name", "") == "" or arg.get("description", "") == "":
                isError = True
                print("Missing name/description for argument in JS function", y["name"], ".\n Arg name is",
                      arg.get("name", ""), ", args description is", arg.get("description", ""))
        y["arguments"] = a.get("params", [])

        returns = a.get("returns", None)[0]
        y["return_value"] = {"description": returns.get("description"),
                             "type": " or ".join(returns.get("type", {}).get("names", []))}
        if y["name"] in markdownDescFuncs:
            y["markdown"] = True
        y["language"] = language
        y["origin"] = origin
        if y["name"] in jsAutomationOnly:
            y["automationOnly"] = True

        x.append(y)
    return x, isError


def createPyDocumentation(path, origin, language):
    isErrorPy = False

    with open(path, 'r') as file:
        pyScript = clean_python_code(file.read(), remove_print_future=False)

    code = compile(pyScript, '<string>', 'exec')
    ns = {'demisto': demistomock}
    exec(code, ns)  # guardrails-disable-line

    x = []

    for a in ns:
        if a != 'demisto' and callable(ns.get(a)) and a not in pyPrivateFuncs:
            docstring = inspect.getdoc(ns.get(a))
            if not docstring:
                print("docstring for function {} is empty".format(a))
                isErrorPy = True
            else:
                y = parser.parse_docstring(docstring)
                y["name"] = a
                y["argList"] = list(inspect.getargspec(ns.get(a)))[0] if pyIrregularFuncs.get(a, None) is None \
                    else pyIrregularFuncs[a]["argList"]

                x.append(y)

    if isErrorPy:
        return None, isErrorPy
    return reformatPythonOutput(x, origin, language)


def createPsDocumentation(path, origin, language):

    isErrorPS = False

    with open(path, 'r') as file:
        ps_script = file.read()

    function_doc_list = list()
    functions_list = re.findall(r'function\s([\w_]*)\s{\s*<#\s*(.*?)#>', ps_script, re.S)

    for function in functions_list:

        function_doc = {
            'language': language,
            'origin': origin
        }
        function_name = function[0]
        function_doc['name'] = function_name
        parameters = function[1].split('.PARAMETER')

        description = parameters[0].split('.DESCRIPTION')[1].strip()
        if not description:
            isErrorPS = True
            print("Missing description for PS function {}.\n".format(function_name))
        function_doc['description'] = description

        arguments = []

        for parameter in parameters[1:]:

            split_param = list(filter(None, parameter.split('\n')))
            required = False
            param_name = split_param[0].strip()
            if 'required' in param_name:
                required = True
                param_name = param_name.replace(' (required)', '')
            param_description = split_param[1]
            if not param_description:
                isErrorPS = True
                print("Missing parameter description for parameter {} for in PS function {}.\n".format(
                    param_name, function_name))
            arguments.append({
                'name': param_name,
                'description': param_description,
                'required': required
            })

        function_doc['arguments'] = arguments
        function_doc_list.append(function_doc)

    return function_doc_list, isErrorPS


def main(argv):
    jsDoc, isErrorJS = createJsDocumentation('./Documentation/commonServerJsDoc.json', 'CommonServerJs', 'javascript')
    pyDoc, isErrorPy = createPyDocumentation('./Scripts/CommonServerPython/CommonServerPython.py',
                                             'CommonServerPython', 'python')
    psDoc, isErrorPS = createPsDocumentation('./Scripts/CommonServerPowerShell/CommonServerPowerShell.ps1',
                                             'CommonServerPowerShell', 'powershell')
    finalDoc = readJsonFile('./Documentation/commonServerConstants.json')

    if isErrorJS or isErrorPy or isErrorPS or not finalDoc:
        print("Errors found in common server docs.")
        sys.exit(1)
    with open('./Documentation/doc-CommonServer.json', 'w') as fp:
        finalDoc += jsDoc
        finalDoc += pyDoc
        finalDoc += psDoc
        json.dump(finalDoc, fp)


if __name__ == "__main__":
    main(sys.argv[1:])
