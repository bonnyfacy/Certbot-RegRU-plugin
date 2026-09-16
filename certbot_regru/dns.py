"""DNS Authenticator for Reg.ru DNS."""
import logging
import time

import json
import requests

import dns.exception
import dns.resolver

import zope.interface

from certbot import errors
from certbot import interfaces
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)

DEFAULT_PROPAGATION_SECONDS = 600
DNS_POLL_INTERVAL_SECONDS = 5
DNS_POLL_NAMESERVERS = ['1.1.1.1', '1.0.0.1']


@zope.interface.implementer(interfaces.IAuthenticator)
@zope.interface.provider(interfaces.IPluginFactory)
class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Reg.ru DNS

    This Authenticator uses the Reg.ru DNS API to fulfill a dns-01 challenge.
    """

    description = 'Obtain certificates using a DNS TXT record (if you are using Reg.ru for DNS).'

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credentials = None

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(
            add, default_propagation_seconds=DEFAULT_PROPAGATION_SECONDS)
        add('credentials', help='Path to Reg.ru credentials INI file', default='/etc/letsencrypt/regru.ini')

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Reg.ru API.'

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            'credentials',
            'path to Reg.ru credentials INI file',
            {
                'username': 'Username of the Reg.ru account.',
                'password': 'Password of the Reg.ru account.',
            }
        )

    def perform(self, achalls):  # pylint: disable=missing-function-docstring
        self._setup_credentials()

        self._attempt_cleanup = True

        responses = []
        pending_records = []
        for achall in achalls:
            domain = achall.domain
            validation_domain_name = achall.validation_domain_name(domain)
            validation = achall.validation(achall.account_key)

            self._perform(domain, validation_domain_name, validation)
            responses.append(achall.response(achall.account_key))
            pending_records.append((validation_domain_name, validation))

        self._wait_for_propagation(pending_records)

        return responses

    def _wait_for_propagation(self, records):
        """
        Polls public DNS resolvers for each added TXT record instead of blindly sleeping for
        the whole propagation-seconds window, so validation proceeds as soon as the records are
        actually visible (falling back to the old fixed wait if they never become visible).
        """
        timeout = self.conf('propagation-seconds')
        deadline = time.time() + timeout

        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = DNS_POLL_NAMESERVERS
        resolver.lifetime = DNS_POLL_INTERVAL_SECONDS
        resolver.timeout = DNS_POLL_INTERVAL_SECONDS

        logger.info('Waiting up to %d seconds for DNS records to propagate...', timeout)

        remaining = list(records)
        while remaining and time.time() < deadline:
            remaining = [
                (name, value) for name, value in remaining
                if not self._txt_record_present(resolver, name, value)
            ]
            if remaining:
                time.sleep(DNS_POLL_INTERVAL_SECONDS)

        if remaining:
            logger.warning(
                'Timed out after %d seconds waiting for DNS propagation of: %s. '
                'Proceeding anyway.',
                timeout, ', '.join(name for name, _ in remaining)
            )
        else:
            # Small buffer: the CA's own validation servers may still lag slightly behind
            # the resolvers we just polled.
            time.sleep(DNS_POLL_INTERVAL_SECONDS)

    @staticmethod
    def _txt_record_present(resolver, name, value):
        query = getattr(resolver, 'resolve', None) or resolver.query
        try:
            answer = query(name, 'TXT')
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.NoNameservers, dns.exception.Timeout):
            return False

        for rdata in answer:
            if b''.join(rdata.strings).decode('utf-8') == value:
                return True
        return False

    def _perform(self, domain, validation_name, validation):
        self._get_regru_client().add_txt_record(validation_name, validation)

    def _cleanup(self, domain, validation_name, validation):
        self._get_regru_client().del_txt_record(validation_name, validation)

    def _get_regru_client(self):
        return _RegRuClient(self.credentials.conf('username'), self.credentials.conf('password'))


class _RegRuClient(object):
    """
    Encapsulates all communication with the Reg.ru
    """

    def __init__(self, username, password):
        self.http = _HttpClient()
        self.options = {
            'username': username,
            'password': password,
            'io_encoding': 'utf8',
            'show_input_params': 1,
            'output_format': 'json',
            'input_format': 'json',
        }

    def add_txt_record(self, record_name, record_content):
        """
        Add a TXT record using the supplied information.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :raises certbot.errors.PluginError: if an error occurs communicating with the Reg.ru API
        """

        data = self._create_params(record_name, {'text': record_content})

        try:
            logger.debug('Attempting to add record: %s', self._redact(data))
            response = self.http.send('https://api.reg.ru/api/regru2/zone/add_txt', data)
        except requests.exceptions.RequestException as e:
            logger.error('Encountered error adding TXT record: %s', e)
            raise errors.PluginError('Error communicating with the Reg.ru API: {0}'.format(e))

        if 'result' not in response or response['result'] != 'success':
            logger.error('Encountered error adding TXT record: %s', response)
            raise errors.PluginError('Error communicating with the Reg.ru API: {0}'.format(response))

        logger.debug('Successfully added TXT record')

    def del_txt_record(self, record_name, record_content):
        """
        Delete a TXT record using the supplied information.
        Note that both the record's name and content are used to ensure that similar records
        created concurrently (e.g., due to concurrent invocations of this plugin) are not deleted.
        Failures are logged, but not raised.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        """

        data = self._create_params(record_name, {
            'record_type': 'TXT',
            'content': record_content
        })

        try:
            logger.debug('Attempting to delete record: %s', self._redact(data))
            response = self.http.send('https://api.reg.ru/api/regru2/zone/remove_record', data)
        except requests.exceptions.RequestException as e:
            logger.warning('Encountered error deleting TXT record: %s', e)
            return

        if 'result' not in response or response['result'] != 'success':
            logger.warning('Encountered error deleting TXT record: %s', response)
            return

        logger.debug('Successfully deleted TXT record.')

    def _create_params(self, domain, input_data):
        """
        Creates POST parameters.
        :param str domain: Domain name
        :param dict input_data: Input data
        :returns: POST parameters
        :rtype: dict
        """
        pieces = domain.split('.')

        input_data['subdomain'] = '.'.join(pieces[:-2])
        input_data['domains'] = [{'dname': '.'.join(pieces[-2:])}]

        data = self.options.copy()
        data.update({'input_data': json.dumps(input_data)})

        return data

    @staticmethod
    def _redact(data):
        """Returns a copy of the request params with the account password masked for logging."""
        redacted = data.copy()
        if 'password' in redacted:
            redacted['password'] = '***'
        return redacted


class _HttpClient(object):
    """
    Encapsulates HTTP requests
    """

    REQUEST_TIMEOUT_SECONDS = 30

    def send(self, url, data):
        """
        Sends a POST request.
        :param str url: URL for the new :class:`Request` object.
        :param dict data: Dictionary (will be form-encoded) to send in the body of the :class:`Request`.
        :raises requests.exceptions.RequestException: if an error occurs communicating with HTTP server
        """

        response = requests.post(url, data=data, timeout=self.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        return response.json()
