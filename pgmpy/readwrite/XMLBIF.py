#!/usr/bin/env python

try:
    from lxml import etree
except ImportError:
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
        except ImportError:
            print("Failed to import ElementTree from any known place")
import numpy as np

from pgmpy.models import BayesianModel
from pgmpy.factors import TabularCPD


class XMLBIFReader:
    """
    Base class for reading network file in XMLBIF format.
    """
    def __init__(self, path=None, string=None):
        """
        Initialisation of XMLBIFReader object.

        Parameters
        ----------
        path : file or str
            File of XMLBIF data
        string : str
            String of XMLBIF data

        Examples
        --------
        # xmlbif_test.xml is the file present in
        # http://www.cs.cmu.edu/~fgcozman/Research/InterchangeFormat/
        >>> reader = XMLBIFReader("xmlbif_test.xml")
        """
        if path:
            self.network = etree.ElementTree(file=path).getroot().find('NETWORK')
        elif string:
            self.network = etree.fromstring(string).find('NETWORK')
        else:
            raise ValueError("Must specify either path or string")
        self.network_name = self.network.find('NAME').text
        self.variables = self.get_variables()
        self.variable_parents = self.get_parents()
        self.edge_list = self.get_edges()
        self.variable_states = self.get_states()
        self.variable_CPD = self.get_cpd()
        self.variable_property = self.get_property()

    def get_variables(self):
        """
        Returns list of variables of the network

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_variables()
        ['light-on', 'bowel-problem', 'dog-out', 'hear-bark', 'family-out']
        """
        variables = [variable.find('NAME').text for variable in self.network.findall('VARIABLE')]
        return variables

    def get_edges(self):
        """
        Returns the edges of the network

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_edges()
        [['family-out', 'light-on'],
         ['family-out', 'dog-out'],
         ['bowel-problem', 'dog-out'],
         ['dog-out', 'hear-bark']]
        """
        edge_list = [[value, key] for key in self.variable_parents
                     for value in self.variable_parents[key]]
        return edge_list

    def get_states(self):
        """
        Returns the states of variables present in the network

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_states()
        {'bowel-problem': ['true', 'false'],
         'dog-out': ['true', 'false'],
         'family-out': ['true', 'false'],
         'hear-bark': ['true', 'false'],
         'light-on': ['true', 'false']}
        """
        variable_states = {variable.find('NAME').text: [outcome.text for outcome in variable.findall('OUTCOME')]
                           for variable in self.network.findall('VARIABLE')}
        return variable_states

    def get_parents(self):
        """
        Returns the parents of the variables present in the network

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_parents()
        {'bowel-problem': [],
         'dog-out': ['family-out', 'bowel-problem'],
         'family-out': [],
         'hear-bark': ['dog-out'],
         'light-on': ['family-out']}
        """
        variable_parents = {definition.find('FOR').text: [edge.text for edge in definition.findall('GIVEN')][::-1]
                            for definition in self.network.findall('DEFINITION')}
        return variable_parents

    def get_cpd(self):
        """
        Returns the CPD of the variables present in the network

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_cpd()
        {'bowel-problem': array([[ 0.01],
                                 [ 0.99]]),
         'dog-out': array([[ 0.99,  0.01,  0.97,  0.03],
                           [ 0.9 ,  0.1 ,  0.3 ,  0.7 ]]),
         'family-out': array([[ 0.15],
                              [ 0.85]]),
         'hear-bark': array([[ 0.7 ,  0.3 ],
                             [ 0.01,  0.99]]),
         'light-on': array([[ 0.6 ,  0.4 ],
                            [ 0.05,  0.95]])}
        """
        variable_CPD = {definition.find('FOR').text: list(map(float, table.text.split()))
                        for definition in self.network.findall('DEFINITION')
                        for table in definition.findall('TABLE')}
        for variable in variable_CPD:
            arr = np.array(variable_CPD[variable])
            arr = arr.reshape((len(self.variable_states[variable]),
                               arr.size//len(self.variable_states[variable])))
            variable_CPD[variable] = arr
        return variable_CPD

    def get_property(self):
        """
        Returns the property of the variable

        Examples
        --------
        >>> reader = XMLBIF.XMLBIFReader("xmlbif_test.xml")
        >>> reader.get_property()
        {'bowel-problem': ['position = (190, 69)'],
         'dog-out': ['position = (155, 165)'],
         'family-out': ['position = (112, 69)'],
         'hear-bark': ['position = (154, 241)'],
         'light-on': ['position = (73, 165)']}
        """
        variable_property = {variable.find('NAME').text: [property.text for property in variable.findall('PROPERTY')]
                             for variable in self.network.findall('VARIABLE')}
        return variable_property

    def get_model(self):
        model = BayesianModel(self.get_edges())

        tabular_cpds = []
        for var, values in self.variable_CPD.items():
            cpd = TabularCPD(var, len(self.variable_states[var]), values,
                             evidence=self.variable_parents[var],
                             evidence_card=[len(self.variable_states[evidence_var])
                                            for evidence_var in self.variable_parents[var]])
            tabular_cpds.append(cpd)

        model.add_cpds(*tabular_cpds)
        return model


class XMLBIFWriter:
    """
    Base class for writing XMLBIF network file format.
    """
    def __init__(self, model_data, encoding='utf-8', prettyprint=True):
        """
        Initialise a XMLBIFWriter object.

        Parameters
        ----------
        model: Model to write
        encoding: String(optional)
            Encoding for text data
        prettyprint: Bool(optional)
            Indentation in output XML if true

        Examples
        -------
        >>> writer = XMLBIFWriter(model)
        """
        self.model = model_data

        self.encoding = encoding
        self.prettyprint = prettyprint

        self.xml = etree.Element("BIF", attrib={'version': '0.3'})
        self.network = etree.SubElement(self.xml, 'NETWORK')
        try:
            etree.SubElement(self.network, 'NAME').text = self.model['network_name']
        except KeyError:
            pass

        self.variables = self.add_variables()
        self.definition = self.add_definition()

    def __str__(self):
        """
        Return the XML as string.
        """
        if self.prettyprint:
            self.indent(self.xml)
        return etree.tostring(self.xml, encoding=self.encoding)

    def indent(self, elem, level=0):
        """
        Inplace prettyprint formatter.
        """
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def add_variables(self):
        """
        Add variables to XMLBIF

        Return
        ---------------
        xml containing variables tag

        Examples
        -------
        >>> writer = XMLBIFWriter(model)
        >>> writer.get_variables()
        """
        variables = self.model['variables']
        variable_tag = {}
        for var in sorted(variables):
            variable_tag[var] = etree.SubElement(self.network, "VARIABLE", attrib={'TYPE': 'nature'})

        variables_states = self.model['states']
        for variable in variables_states:
            for state in variables_states[variable]:
                etree.SubElement(variable_tag[variable], "OUTCOME").text = state

        variables_property = self.model['property']
        for variable in variables_property:
            for property_var in variables_property[variable]:
                etree.SubElement(variable_tag[variable], "PROPERTY").text = property_var
        return variable_tag

    def add_definition(self):
        """
        Add Definition to XMLBIF

        Return
        ---------------
        xml containing definition tag

        Examples
        -------
        >>> writer = XMLBIFWriter(model)
        >>> writer.add_definition()
        """
        parents = self.model['parents']
        definition_tag = {}
        for var in sorted(parents):
            definition_tag[var] = etree.SubElement(self.network, "DEFINITION")
            etree.SubElement(definition_tag[var], "FOR").text = var
            for child in sorted(parents[var]):
                etree.SubElement(definition_tag[var], "GIVEN").text = child

        return definition_tag
