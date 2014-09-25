# coding=utf-8
__author__ = "Type-A Machines"


# TYPEA: octoprint/wifi.py: various classes and functions for altering the wifi settings of the OS.
#   Based on <https://github.com/rockymeza/wifi>. Modifications necessary because the implementation of iwlist and ifup
#   on our devices is slightly different in format than what the original code expects. Differences from orginal source
#   (mostly) noted.
# 
# TYPEA: the code in this file is copied or based on code from <https://github.com/rockymeza/wifi>. BSD license for
#     original code:
 
# Copyright (c) 2012, Gavin Wahl <gavinwahl@gmail.com>, Rocky Meza <rockymeza@gmail.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# softwARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# TYPEA: useful information:
#   Details on the format of the /etc/network/interfaces file:
#   <http://unix.stackexchange.com/questions/102530/escape-characters-in-etc-network-interfaces>

import itertools
import logging, logging.config
import os
import re
import subprocess
import sys
import textwrap

from copy import deepcopy
from pbkdf2 import PBKDF2

# #mark TYPEA: based on wifi/utils.py

def ensure_file_exists(filename):
    """
    http://stackoverflow.com/a/12654798/1013960
    """
    if not os.path.exists(filename):
        open(filename, 'a').close()



#	TYPEA: from wifi/exceptions.py

class ConnectionError(Exception):
    pass


class InterfaceError(Exception):
    pass
    

class AuthenticationError(Exception):
    pass



# #mark TYPEA: based on wifi/scan.py

class Cell(object):
    """
    Presents a Python interface to the output of iwlist.
    """

    nextCellID = 0

    # TYPEA: since SSIDs can't be uniqued by name, we need a way to identify a particular cell object. Thus, we've
    #      added a quick and dirty serial number sort of ID. Every new Cell gets a unique ID, and 0 is the invalid ID
    #      value.

    @classmethod
    def newCellID(cls):
        cls.nextCellID += 1
        return cls.nextCellID


    # TYPEA: default init to initialize ID number.
    def __init__(self):
        self._id = Cell.newCellID()


    def __repr__(self):
        return 'Cell(ssid={ssid})'.format(**vars(self))


    @classmethod
    def all(cls, interface):
        """
        Returns a list of all cells extracted from the output of iwlist.
        """
        try:
            iwlist_scan = subprocess.check_output(['/sbin/iwlist', interface, 'scan'], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise InterfaceError(e.output.strip())
        else:
            iwlist_scan = iwlist_scan.decode('utf-8')
        
        cells = map(Cell.from_string, cells_re.split(iwlist_scan)[1:])

        return cells


    # TYPEA: different from original: new function, returns visible cells (i.e. cells that don't have an empty or bogus
    #		SSID)
    @classmethod
    def visible(cls, interface):
    	namedCells = cls.where(interface, lambda cell: cell.ssid and (len(cell.ssid) > 0))
    	
    	visibleCells = []
    	for namedCell in namedCells:
    	    #   TYPEA: unique cells by name in our list of visible cells. This seems like it might be wrong; there's
    	    #       no reason two wifi networks can't have the same name. In practice, though, it doesn't matter.
    	    #       There's no persistable way to identify a wifi network except its name, and even if there were,
    	    #       wpa_supplicant only takes a name as a network ID. So, even if we distinguish between two networks of
    	    #       the same name, we'd still end up connecting to whichever one wpa_supplicant picked.
    	    #
    	    #       Also, this method of uniquing is pretty brute-force. The data set ought to be small, though, so it
    	    #       shouldn't matter. And a consistent method for comparing and hashing the Cell class (so we could put
    	    #       Cells into a set or dict for fast uniquing) isn't obvious.
    	    dupes = filter(lambda visibleCell: visibleCell.ssid.lower() == namedCell.ssid.lower(), visibleCells)
    	    if len(dupes) == 0:
    	        visibleCells.append(namedCell)
    	
    	return visibleCells
    	

    @classmethod
    def from_string(cls, cell_string):
        """
        Parses the output of iwlist scan for one cell and returns a Cell
        object for it.
        """
        return normalize(cell_string)


    @classmethod
    def where(cls, interface, fn):
        """
        Runs a filter over the output of :meth:`all` and the returns
        a list of cells that match that filter.
        """
        
        return list(filter(fn, cls.all(interface)))


    # TYPEA: id number accessor.
    @property
    def id(self):
        return self._id



cells_re = re.compile(r'Cell \d+ - ')
identity = lambda x: x

key_translations = {
    'encryption key': 'encrypted',
    'essid': 'ssid',
}


def normalize_key(key):
    key = key.strip().lower()

    key = key_translations.get(key, key)

    return key.replace(' ', '')


normalize_value = {
    'ssid': lambda v: v.strip('"'),
    'encrypted': lambda v: v == 'on',
    'address': identity,
    'mode': identity,
}


def split_on_colon(string):
    key, _, value = map(lambda s: s.strip(), string.partition(':'))

    return key, value


def normalize(cell_block):
    # The cell blocks come in with every line except the first indented at
    # least 20 spaces.  This removes the first 20 spaces off of those lines.
    lines = textwrap.dedent(' ' * 20 + cell_block).splitlines()
    cell = Cell()

    # TYPEA: different from original: removed parsing of all the values we don't care about.

    while lines:
        line = lines.pop(0)

        if ':' in line:
            key, value = split_on_colon(line)
            key = normalize_key(key)

            if key == 'ie':
                if 'Unknown' in value:
                    continue

                # consume remaining block
                values = [value]
                while lines and lines[0].startswith(' ' * 4):
                    values.append(lines.pop(0).strip())

                if 'WPA2' in value:
                    cell.encryption_type = 'wpa2'
                elif 'WPA' in value:
                    cell.encryption_type = 'wpa'
            if key in normalize_value:
                setattr(cell, key, normalize_value[key](value))

    # It seems that encryption types other than WEP need to specify their
    # existence.
    if cell.encrypted and not hasattr(cell, 'encryption_type'):
        cell.encryption_type = 'wep'

    return cell



# TYPEA: convenience functions for Octoprint support

def find_cell(interface, ssid):
    cells = Cell.where(interface, lambda cell: cell.ssid.lower() == ssid.lower())

    try:
        cell = cells[0]
    except IndexError:
        cell = None

    return cell



# #mark TYPEA: based on wifi/scheme.py

# TYPEA: different from original: renamed configuration() function to avoid confusion. Also reworked, a bit. PSK
#      generation no longer happens when generating options for a cell. It's deferred until scheme activation.
def options_for_cell(cell):
    """
    Returns a dictionary of configuration options for a cell
    """
    if not cell.encrypted:
        return {
            'wireless-essid': cell.ssid,
        }
    else:
        if cell.encryption_type.startswith('wpa'):
            return {
                'wpa-ssid': cell.ssid,
            }
        elif cell.encryption_type == 'wep':
            return {
                'wireless-essid': cell.ssid,
            }
        else:
            raise NotImplementedError


# TYPEA: different from original: new function that returns the ssid from a dictionary of interface config options.
#      We normalize the SSID because according to the internet, wpa_supplicant permits leading/trailing double quotes
#      around SSIDs. According to the spec, though, double quotes aren't valid in SSIDs. So we leave the quotes on the
#      SSID in the options, since that's the string that will get written to the config file and/or passed to
#      wpa_supplicant (via ifdown and ifup) but we remove leading/trailing quotes for other uses of the SSID.
def ssid_from_options(options):
    if not options:
        return None

    if 'wpa-ssid' in options:
        return options['wpa-ssid']
    if 'wireless-essid' in options:
        return options['wireless-essid']

    return None


# TYPEA: different from original: ifup on our Beagle doesn't return the IP address in its output, so we check the
#      output of ifconfig for an IP address instead. This following regexp has been adjusted accordingly.
bound_ip_re = re.compile(r'^\s+inet addr:(?P<ip_address>\S+)', flags=re.MULTILINE)


class Scheme(object):
    """
    Saved configuration for connecting to a wireless network.  This
    class provides a Python interface to the /etc/network/interfaces
    file.
    """

    # TYPEA: different from original: renamed "interfaces" class var to osInterfacesFile, for sanity's sake.
    osInterfacesFile = '/etc/network/interfaces'


    @classmethod
    def for_file(cls, interfaces):
        """
        A class factory for providing a nice way to specify the interfaces file
        that you want to use.  Use this instead of directly overwriting the
        interfaces Class attribute if you care about thread safety.
        """
        return type(cls)(cls.__name__, (cls,), {
            'osInterfacesFile': interfaces,
        })


    def __init__(self, interface, ssid, configOptions):
        # TYPEA: different from original: privatized ivars. Renamed "name" ivar to "_ssid", for sanity's sake.
        self._interface = interface
        self._ssid = ssid.strip('"')
        self._options = configOptions
        
        # TYPEA: normalize the passkey by stripping double quotes from it.
        if self._options:
            passkey = self.passkey
            if passkey:
                self.passkey = passkey.strip('"')
        


    def __str__(self):
        """
        Returns the representation of a scheme that you would need
        in the /etc/network/interfaces file.
        """

        # TYPEA: different from original: output interface line in the same format our Beagle's iwlist uses.
        iface = "iface {0} inet dhcp".format(self.interface)
        configOptions = ''.join('\n    {k} "{v}"'.format(k=k, v=v) for k, v in self.options.iteritems())
        return iface + configOptions + '\n'


    def __repr__(self):
        return 'Scheme(interface={0!r}, ssid={1!r}, options={2!r}'.format(self.interface, self.ssid, self.options)


    # TYPEA: different from original: make interface property readonly.
    @property
    def interface(self):
        return self._interface


    # TYPEA: different from original: make ssid property readonly.
    @property
    def ssid(self):
        return self._ssid


    # TYPEA: different from original: make options property readonly.
    @property
    def options(self):
        return self._options


    # TYPEA: different from original: new property, return the human-readable passkey of the scheme. Unlike the
    #      original, we persist the readable passkey for WPA networks, not the encrypted PSK. This seems... insecure,
    #      but it also seems to be standard practice on linux, and keeping the human-readable passkey around greatly
    #      simplifies passkey handling in Octoprint's UI.
    @property
    def passkey(self):
        key = self.passkey_id
        if key in self._options:
            return self._options[key]

        return ""


    @passkey.setter
    def passkey(self, value):
        key = self.passkey_id
        if value and len(value) > 0:
            # TYPEA: normalize the passkey by stripping double quotes from it.
            passkey = value.strip('"')
            self._options[key] = passkey
        else:
            self._options.pop(key, None)


    # TYPEA: different from original: new property, return the ID string of the passkey option for this Scheme.
    @property
    def passkey_id(self):
        if self.encryption_type == 'wpa':
            return 'wpa-psk'

        # TYPEA: default to WEP encryption.
        return 'wireless-key'


    # TYPEA: different from original: new property, return the PSK of the scheme. WPA networks take an encrypted
    #      passkey, so we return that if the scheme is WPA-encrypted. For other network types, the PSK is the same as
    #      the passkey.
    # 
    #      Note that the 64 character length check is to identify passkeys that have already been encrypted. According
    #      to the WPA spec, user passkeys must be less than 64 characters, and the encrypted passkey must be exactly
    #      64 characters.
    @property
    def psk(self):
        psk = self.passkey
        pskLen = len(psk)
        if pskLen > 0 and self.encryption_type == 'wpa':
            if pskLen != 64:
                psk = PBKDF2(psk, self.ssid, 4096).hexread(32)

        return psk


    # TYPEA: different from original: new property, return the security protocol of the scheme.
    @property
    def encryption_type(self):
        if 'wpa-ssid' in self._options:
            return 'wpa'
        elif 'wpa-psk' in self._options:
            return 'wpa'
        elif 'wireless-key' in self._options:
            return 'wep'

        return "unknown"


    # TYPEA: different from original: new method, determines if the provided information matches the various properties
    #       of this scheme. Used determine if user-provided input requires changing the device network config.
    def matches(self, interface, ssid, passkey):
        if interface != self.interface:
            return False
            
        if ssid != self.ssid:
            return False
            
        selfPasskey = self.passkey
        if (passkey != selfPasskey) or (not passkey and len(selfPasskey) > 0):
            return False

        cell = find_cell(interface, ssid)
        if cell and cell.encryption_type.startswith('wpa') and self.encryption_type != 'wpa':
            return False;

        return True


    # TYPEA: different from original: new method. Return the options necessary to connect to the Scheme's interface
    #      using ifup.
    def options_for_ifup(self):
        # TYPEA: make a deep copy of the options, because we're possibly going to add/change some options solely for
        #      the sake of invoking ifup.
        ifupOptions = deepcopy(self._options)

        #  TYPEA: replace the passkey with the PSK. If the network is WPA, the PSK is the encrypted version of the
        #      passkey.
        psk = self.psk
        if psk:
            ifupOptions[self.passkey_id] = psk

        if self.encryption_type != 'wep':
            # TYPEA: why do we not set auto channel on encrypted WEP nets? This logic is carried over from original
            #      code (see the configuration() function) but it seems weird.
            ifupOptions['wireless-channel'] = 'auto'
     
        return ifupOptions


    # TYPEA: different from original: new method, replaces Scheme.as_args(). Return the options necessary to connect
    #      to the Scheme's interface using ifup.
    def ifup_args(self):
        options = self.options_for_ifup()
        args = list(itertools.chain.from_iterable(
            ('-o', '{k}={v}'.format(k=k, v=v)) for k, v in options.items()))

        # TYPEA: different from original: ifup on our Beagle uses slightly different args format.
        return [self.interface] + args


    @classmethod
    def all(cls):
        """
        Returns an array of saved schemes.
        """

        # TYPEA: different from original: replaced extract_schemes() with schemes_from_file().
        return schemes_from_file(cls.osInterfacesFile, scheme_class=cls)


    @classmethod
    def where(cls, fn):
        return filter(fn, cls.all())


    # TYPEA: different from original: new class method. Loads the scheme for the specified interface from the
    #      interfaces config file. Returns None if the interface isn't in the config file.
    @classmethod
    def for_interface(cls, interface):
        try:
            return cls.where(lambda s: s.interface == interface)[0]
        except IndexError:
            return None


    @classmethod
    def for_cell(cls, interface, cell, passkey = None):
        """
        Intuits the configuration needed for a specific
        :class:`Cell` and creates a :class:`Scheme` for it.
        """
        
        scheme = cls(interface, cell.ssid, options_for_cell(cell))
        if passkey:
            scheme.passkey = passkey

        return scheme


    # TYPEA: different from original: new method. Adds supports for replacing an existing configuration. Also supports
    #   writing to files that aren't /etc/network/interfaces, which is handy for not blowing up the Beagle while testing
    #   this code. 
    def save_to_file(self, file, autoConnect = True):
        with open(file, 'r+') as f:
            fileLines = f.readlines()
            
            # TYPEA: get the stanza for this interface as an array of lines.
            stanzaLines = str(self).splitlines(True)

            # TYPEA: prepend the autoconnect stanza if that's what the caller wants.
            if autoConnect:
                autoStanza = "auto %s" % (self.interface) + '\n'
                stanzaLines.insert(0, autoStanza)
            
            # TYPEA: remove any existing stanzas for this interface, since we're going to be rewriting it.
            remove_interface_stanza(self.interface, fileLines)
            
            # TYPEA: get all the remaining stanzas, sorted by line number.
            sortedStanzas = order_stanzas(find_interface_stanzas(fileLines, True))
            
            # TYPEA: figure out where in the file we're going to insert the new stanza. If there are stanzas for other
            #   interfaces, then we write out our stanza before them. If there aren't any other stanzas, then we append
            #   our stanze to the end of the file.

            if len(sortedStanzas) > 0:
                # TYPEA: add a trailing newline for prettiness.
                stanzaLines.append("\n")
                
                # TYPEA: set our insertion location to the start line of the first other interface stanza.
                firstStanza = sortedStanzas[0]
                startLine = firstStanza['startLine']
            else:
                # TYPEA: no other interface stanzas in the file, so our insertion location is the end of the file.
                startLine = len(fileLines)
                if fileLines[startLine - 1].strip():
                    # TYPEA: add a preceding newline for prettiness since the last line in the file isn't whitespace.
                    stanzaLines.insert(0, "\n")
                    startLine += 1
           
            # TYPEA: insert the new stanza into the file.
            for lineIndex in range(len(stanzaLines)):
                insertIndex = startLine + lineIndex
                fileLines.insert(insertIndex, stanzaLines[lineIndex])

            # TYPEA: reassemble the file content.
            content = ""
            for line in fileLines:
                content += line

            # TYPEA: write out the new file content.
            f.seek(0)
            f.write(content)
            f.truncate()


    # TYPEA: different from original: added autoconnect support, reworked to call save_to_file().
    def save(self, autoConnect = True):
        """
        Writes the configuration to the :attr:`osInterfacesFile` file.
        """

        self.save_to_file(self.osInterfacesFile, autoConnect)


    # TYPEA: different from original: new class method, mostly for testing purposes.
    @classmethod
    def save_all_to_file(cls, file):
        """
        Writes all scheme configurations to the specified file.
        """

        schemes = cls.all()

        for scheme in schemes:
            scheme.save_to_file(file)


    # TYPEA:  different from original. Adds supports deleteing a Scheme from files that aren't /etc/network/interfaces,
    #      which is handy for not blowing up the Beagle while testing this code.
    def delete_from_file(self, file):
        """
        Deletes the configuration from the specified file.
        """
 
        with open(file, 'r+') as f:
            fileLines = f.readlines()

            # TYPEA: remove our interface from the file's line array.
            if not remove_interface_stanza(self.interface, fileLines):
                return


            # TYPEA: reassemble the file content without the deleted lines
            content = ""
            for line in fileLines:
                content += line

            # TYPEA: write out the new file content.
            f.seek(0)
            f.write(content)
            f.truncate()


    # TYPEA: different from original: reworked to call delete_from_file.
    def delete(self):
        """
        Deletes the configuration from the :attr:`osInterfacesFile` file.
        """
 
        self.delete_from_file(self.osInterfacesFile)


    # TYPEA: different from original: takes an optional passkey parameter. If no passkey is supplied, then the
    #      connection is attempted with the passkey from the Scheme's options. Otherwise, the passkey is set into the
    #      the Scheme's options before the connection attempt.
    def activate(self, passkey = None):
        """
        Connects to the network as configured in this scheme.
        """
        if passkey:
            self.passkey = passkey

        print 'Scheme.activate(): passkey = {}.'.format(self.passkey)

        try:
            subprocess.check_output(['/sbin/ifdown', self.interface], stderr=subprocess.STDOUT)
            print 'Scheme.activate(): ifdown succeeded.'
        except subprocess.CalledProcessError as e:
            print 'Scheme.activate(): exception caught: {}.'.format(e)
            raise InterfaceError(e.output.strip())

        try:
            # TYPEA: different from original: ifup on our Beagle doesn't return the IP address in its output, so we ignore
            #      its output and call ifconfig to determine if we have a valid IP (meaning the connection succeeded).
            subprocess.check_output(['/sbin/ifup'] + self.ifup_args(), stderr=subprocess.STDOUT)
            print 'Scheme.activate(): ifup succeeded.'
        except subprocess.CalledProcessError as e:
            raise InterfaceError(e.output.strip())

        # TYPEA: different from original: call ifconfig.
        ifconfig_output = subprocess.check_output(['/sbin/ifconfig', self.interface], stderr=subprocess.STDOUT)
        ifconfig_output = ifconfig_output.decode('utf-8')
        print 'Scheme.activate(): ifconfig succeeded.'

        return self.parse_ifconfig_output(ifconfig_output)


    # TYPEA: different from original: parse ifconfig output, not ifup
    def parse_ifconfig_output(self, output):
        matches = bound_ip_re.search(output)
        if matches:
            return Connection(scheme=self, ip_address=matches.group('ip_address'))
        else:
            # TYPEA: if ifup succeeded, but we didn't get an IP, then assume authentication failed. That seems to be
            #      the only indication of authentication failures on our Beagle.
            raise AuthenticationError("Failed to connect to %r" % self)



class Connection(object):
    """
    The connection object returned when connecting to a Scheme.
    """
    def __init__(self, scheme, ip_address):
        self.scheme = scheme
        self.ip_address = ip_address

     # TYPEA: different from original: added __repr__ for easier logging.
    def __repr__(self):
        return 'Connection(interface = "{0}", ssid = "{1}", IP = {2})'.format(self.scheme.interface, self.scheme.ssid, self.ip_address)


#  TYPEA: new and improved interface config parsing utilities.

# TYPEA: different from original: new function: replaces extract_schemes(...). Returns an array containing all Schemes
#   in the specified file
def schemes_from_file(file, scheme_class=Scheme):
    schemes = []

    ensure_file_exists(file)
    with open(file, 'r') as f:
        stanzas = order_stanzas(find_interface_stanzas(f.readlines(), True))    
        for stanza in stanzas:
            scheme = scheme_class(stanza['interface'], stanza['ssid'], stanza['options'])
            schemes.append(scheme)

    return schemes


#  TYPEA: different from original: add regexps for finding both wlan** and ra** interfaces since our Beagle seems to
#      want wifi on ra0.
#  TYPEA: orginal regexp for reference purposes:
#
#      scheme_re = re.compile(r'iface\s+(?P<interface>wlan\d?)(?:-(?P<name>\w+))?')

wlan_re = re.compile(r'iface\s+(?P<interface>wlan\d?)(?:-(?P<name>\w+))?')
ra_re = re.compile(r'iface\s+(?P<interface>ra\d?)(?:-(?P<name>\w+))?')

#  TYPEA: FIXME: note the above regexps are slightly wrong for the version of iwlist that we use. The line listing the
#      interface we get back from iwlist only contains the interface and not the name. Someone who knows regexp better
#      should adjust the above regexps accordingly (my attempts to fix them broke them >.<), but since they parse to
#      named groups, they still work for our purposes.


# TYPEA: different from original: new function that parses the lines of a config file and returns information about all
#      the wifi interface stanzas they contain:
# 
#          interface: the network interface ID
#          ssid: the ssid of the interface.
#          options: the configuration options for the interface (i.e. passkey, auto-channel, etc.)
#          hasAuto: flag indicating if the interface is set to autoconnect on device boot.
#          startLine: the line in the file at which the stanzas defining the interface start.
#          lineCount: the number of lines in the stanzas defining the interface. Contiguous from startLine.
#          hasTrailingWS: whether the stanzas defining the interface are followed by a blank line that's safe to delete.
#
#      Note that duplicates are parsed and returned. There should never be dupes, but... standard practice for setting
#      up our devices has involved hand-editing /etc/network/interfaces, and users do crazy things. Thus, the format of
#      the results is a dictionary of arrays. The keys for the dictionary are the interface IDs, and the values are an
#      array containing one or more dictionaries containing the values listed above.
#
#      Also note that only well-formed stanzas are returned. If an interface stanza doesn't have properly formatted
#      options or if the options  don't contain the ssid, then that stanza isn't recorded in the results.
def find_interface_stanzas(lines, countTrailingWS):
    lineCount = len(lines)
    index = 0
    stanzas = {}

    for index in range(0, lineCount):
        line = lines[index]

        # TYPEA: the interface defined by the stanza.
        interface = None

        # TYPEA: determine if this line starts an interface stanza.
        if line and not line.startswith('#'):
            # TYPEA: use our interface regexps to figure out if this is the start of a stanza.
            match = wlan_re.match(line)
            if not match:
                match = ra_re.match(line)
            if match:
                interface = match.group('interface')

        if not interface:
            # TYPEA: no interface definition, so onto the next line.
            continue

        # TYPEA: the starting line of the stanza.
        stanzaStartLine = index;

        # TYPEA: the number of lines in the stanza.
        stanzaLineCount = 1

        # TYPEA: the interface options defined by the stanza.
        options = {}

        # TYPEA: parse the options for the interface and adjust things accordingly.
        optionIndex = index + 1
        while optionIndex < lineCount and lines[optionIndex].startswith(' '):
            key, value = re.sub(r'\s{2,}', ' ', lines[optionIndex].strip()).split(' ', 1)
            options[key] = value
            stanzaLineCount += 1
            optionIndex += 1

        if len(options) == 0:
            # TYPEA: no options, so onto the next line.
            continue

        ssid = ssid_from_options(options)
        if not ssid:
            # TYPEA: no ssid, so onto the next line.
            continue

        # TYPEA: whether the stanza has an autoconnect stanza before it.
        hasAutoConnect = False

        # TYPEA: figure out if the autoconnect specifier is set and adjust things accordingly.
        prevLine = None
        if index > 0:
            prevLine = lines[index - 1]
            autoConnect = "auto %s" % (interface)
            if prevLine.strip() == autoConnect:
                hasAutoConnect = True
                stanzaStartLine = index - 1
                stanzaLineCount += 1
                if (index > 1):
                    prevLine = lines[index - 2]

        # TYPEA: whether the stanza has the trailing whitespace that can be counted as part of it.
        hasTrailingWS = False

        # TYPEA: extend the entry to account for trailing whitespace if the caller wants.
        if countTrailingWS:
            # TYPEA: extend the range of the stanza by one line to account for trailing whitespace if we can.
            #      If the lines before and after the entry are whitespace, then we count the line after as part of
            #      the entry.
            indexAfterStanza = optionIndex
            if indexAfterStanza < lineCount:
                if not lines[indexAfterStanza].strip():
                    if not prevLine or not prevLine.strip():
                        hasTrailingWS = True
                        stanzaLineCount += 1

        # TYPEA: put all the stanza info into a dict.
        stanza = {
            'interface': interface,
            'ssid': ssid,
            'options': options,
            'hasAuto': hasAutoConnect,
            'startLine': stanzaStartLine,
            'lineCount': stanzaLineCount,
            'hasTrailingWS': hasTrailingWS
        }

       # TYPEA: put the stanza in our collection of results. Note that we allow for duplicate stanzas. The result is a
       #    dictionary of arrays.           
        if interface in stanzas:
            stanzas[interface].append(stanza)
        else:
            stanzas[interface] = [stanza]

    return stanzas


# TYPEA: different from original: new function that flattens the results of find_interface_stanzas into an array
#      sorted by the start line of the stanzas.
def order_stanzas(stanzas):
    sortedStanzas = []

    if len(stanzas) > 0:
        for ifaceStanzas in stanzas.itervalues():
            sortedStanzas.extend(ifaceStanzas)
        sortedStanzas.sort(key = lambda stanza: stanza['startLine'])
        
    return sortedStanzas


# TYPEA: different from original: new function that removes an interface definition stanza from a file. Removes dupes,
#      too. Returns if lines were actually deleted.
def remove_interface_stanza(interface, lines):
    stanzas = find_interface_stanzas(lines, True)
    if not interface in stanzas:
        return False

    # TYPEA: get the iface stanza dict (or dicts, if there are dupes)
    stanzasToDelete = stanzas[interface]
    linesToDelete = []

    # TYPEA: gather the lines to delete
    for stanza in stanzasToDelete:
        startLine = stanza["startLine"]
        lineCount = stanza["lineCount"]
        linesToDelete.extend(range(startLine, startLine + lineCount))

    # TYPEA: delete the lines.
    if (len(linesToDelete) > 0):
        linesToDelete.sort()
        for lineToDelete in reversed(linesToDelete):
            lines.pop(lineToDelete)

    return True



# TYPEA: WifiManager: wrapper class around the state necessary to support wifi settings, we don't have to pollute
#       server.py with a lot of new globals.

class WifiManager(object):

    def __init__(self, printer):
    	print "WifiManager initialized."
        self._printer = printer


    def interfaceIP(self, interface):
        output = subprocess.check_output(['/sbin/ifconfig', interface], stderr=subprocess.STDOUT)
        output = output.decode('utf-8')

        matches = bound_ip_re.search(output)
        if matches:
           return matches.group('ip_address')

        return None


    def interfaceIsConnected(self, interface):
        ip = self.interfaceIP(interface)
        if ip:
            return (len(ip) > 0)
        
        return False


    def disconnect(self, interface):
        try:
            subprocess.check_output(['/sbin/ifdown', interface], stderr=subprocess.STDOUT)
        except:
            pass


    def defaultSettings(self, interface):
        if not interface:
            return None

        return {
            'wifiInterface': interface,
            'wifiNoneSelected': True,
            'wifiSelectedSSID': '',
            'wifiPasskey': ''
        }


    def getSettings(self, interface):
        logger = logging.getLogger(__name__)
        print 'WifiManager.getSettings() called for interface "{0}".'.format(interface)

        settingsDict = self.defaultSettings(interface)
        if not settingsDict:
            return None

        selectedSSID = ""
        passkey = ""
        noneSelected = True
        visibleSSIDs = []

        currentScheme = Scheme.for_interface(interface)
        if currentScheme:
            passkey = currentScheme.passkey
            selectedSSID = currentScheme.ssid
            noneSelected = False
#           print 'WifiManager.getSettings(): current scheme = {0}'.format(currentScheme)

        visibleCells = Cell.visible(interface)
        if visibleCells:
            for cell in visibleCells:
                ssidInfo = {'id': cell.id, 'name': cell.ssid}
                visibleSSIDs.append(ssidInfo)
 #              print 'WifiManager.getSettings(): visible cell detected: (id: {0}, name: {1}).'.format(ssidInfo['id'], ssidInfo['name'])

        settingsDict['wifiInterface'] = interface
        settingsDict['wifiIPAddress'] = self.interfaceIP(interface)
        settingsDict['printerIsPrinting'] = self._printer.isPrinting()
        settingsDict['wifiNoneSelected'] = noneSelected
        settingsDict['wifiSelectedSSID'] = selectedSSID
        settingsDict['wifiPasskey'] = passkey
        settingsDict['wifiVisibleSSIDs'] = visibleSSIDs

        print 'WifiManager.getSettings(): final settings dict: {}.'.format(settingsDict)
        
        return settingsDict


    def needsSettingsChange(self, interface, requestData):
        logger = logging.getLogger(__name__)
        logger.info("WifiManager.needsSettingsChange() called")
        print 'WifiManager.needsSettingsChange() called for interface "{0}".'.format(interface)
        print 'WifiManager.needsSettingsChange(): requestData = {}.'.format(requestData)

        needsWifiConnect = False
        needsWifiDisconnect = False
        needsWifiSwitch = False
        needsWifiDelete = False
        noneSelected = False
        validRequest = True

        if requestData:
            selectedSSID = ""
            passkey = ""
            noneSelected = False

            if 'wifiSelectedSSID' in requestData:
                selectedSSID = requestData['wifiSelectedSSID']
            if 'wifiPasskey' in requestData:
                passkey = requestData['wifiPasskey']
            if 'wifiNoneSelected' in requestData:
                noneSelected = requestData['wifiNoneSelected']
            if not noneSelected:
                validRequest = (len(selectedSSID) > 0)

            if validRequest:        
                currentScheme = Scheme.for_interface(interface)
                if noneSelected:
                    needsWifiDelete = (currentScheme != None)
                    needsWifiDisconnect = self.isConnected
                else:
                    if not currentScheme or not currentScheme.matches(interface, selectedSSID, passkey):
                        if self.interfaceIsConnected(interface):
                            needsWifiSwitch = True
                        else:
                            needsWifiConnect = True

        responseDict = {
            'wifiInterface': interface,
            'wifiIPAddress': self.interfaceIP(interface),
            'printerIsPrinting': self._printer.isPrinting(),
            'wifiNeedsChangeFlags': {
                'needsWifiConnect': needsWifiConnect,
                'needsWifiDisconnect': needsWifiDisconnect,
                'needsWifiSwitch': needsWifiSwitch,
                'needsWifiDelete': needsWifiDelete,
            }
        }

        print 'WifiManager.needsSettingsChange(): response dict: {}.\n'.format(responseDict)
        
        return responseDict


    def setSettings(self, interface, requestData):
        logger = logging.getLogger(__name__)
        logger.info("WifiManager.setSettings() called")

        validRequest = True
        succeeded = False
        authenticateFailed = False
        ssidNotFound = False
        osFailure = False
        ipAddress = self.interfaceIP(interface)

        if requestData:
            selectedSSID = ""
            passkey = ""
            noneSelected = False

            if 'wifiSelectedSSID' in requestData:
                selectedSSID = requestData['wifiSelectedSSID']
            if 'wifiPasskey' in requestData:
                passkey = requestData['wifiPasskey']
            if 'wifiNoneSelected' in requestData:
                noneSelected = requestData['wifiNoneSelected']
            if not noneSelected:
                validRequest = (len(selectedSSID) > 0)

            if validRequest:
                if noneSelected:
                    currentScheme = Scheme.for_interface(interface)
                    if currentScheme:
                        try:
                            currentScheme.delete()
                            if len(ipAddress) > 0:
                                ipAddress = ""
                                self.disconnect(interface)
                            succeeded = True
                        except:
                            osFailure = True
                    else:
                        succeeded = True
                else:
                    selectedCell = find_cell(interface, selectedSSID)

                    if selectedCell:
                        newScheme = Scheme.for_cell(interface, selectedCell, passkey)
                        try:
                            connection = newScheme.activate()
                            newScheme.save()
                            succeeded = True
                            ipAddress = connection.ip_address
                        except AuthenticationError:
                            authenticateFailed = True
                            ipAddress = ""
                        except:
                            osFailure = True
                    else:
                        ssidNotFound = True                

        responseDict = {
            'wifiInterface': interface,
            'wifiIPAddress': ipAddress,
            'printerIsPrinting': self._printer.isPrinting(),
            'wifiSettingsChangeResultFlags': {
                'succeeded': succeeded,
                'invalidRequest': (not validRequest),
                'authenticateFailed': authenticateFailed,
                'ssidNotFound': ssidNotFound,
                'osFailure': osFailure
            }
        }
        
        print 'WifiManager.setSettings(): response dict: {}.\n'.format(responseDict)

        return responseDict
