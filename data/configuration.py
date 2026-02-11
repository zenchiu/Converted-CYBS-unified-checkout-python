"""
Merchant configuration properties for CyberSource REST API.
Reads credentials from ../config.ini (one level above the app directory).
"""

import os
import configparser

from CyberSource.logging.log_configuration import LogConfiguration


def _load_config():
    """Load the config.ini file from the project root."""
    config = configparser.ConfigParser()
    # config.ini lives one level above unified-checkout-python/
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.ini"
    )
    if not os.path.exists(config_path):
        # Fallback: try same level as the app directory
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.ini"
        )
    config.read(config_path)
    return config


class MerchantConfiguration:
    def __init__(self):
        cfg = _load_config()

        # CyberSource credentials from config.ini
        self.authentication_type = "http_signature"
        self.merchant_id = cfg.get("CyberSource", "merchant_id", fallback="")
        self.merchant_key_id = cfg.get("CyberSource", "key_id", fallback="")
        self.merchant_secret_key = cfg.get("CyberSource", "secret_key", fallback="")
        self.run_environment = cfg.get(
            "CyberSource", "run_environment", fallback="apitest.cybersource.com"
        )

        # App settings
        self.port = cfg.getint("App", "port", fallback=5000)

        # JWT parameters
        self.keys_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "Resource"
        )

        # Meta key parameters
        self.use_metakey = False
        self.portfolio_id = ""

        # Connection timeout
        self.timeout = 1000

        # Logging parameters
        self.enable_log = True
        self.log_file_name = "cybs"
        self.log_maximum_size = 5242880  # 5 MB
        self.log_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "log"
        )
        self.log_level = "Debug"
        self.enable_masking = True
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.log_date_format = "%Y-%m-%d %H:%M:%S"

        # MLE (Message Level Encryption) - disabled by default
        self.useMLEGlobally = False

        # PEM Key file path for decoding JWE Response (optional)
        self.jwe_pem_file_directory = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "Resource",
            "NetworkTokenCert.pem",
        )

        # Override the default developerId (optional)
        self.default_developer_id = ""

    def get_configuration(self):
        """Return configuration as a dictionary for the CyberSource API client."""
        configuration_dictionary = {}
        configuration_dictionary["authentication_type"] = self.authentication_type
        configuration_dictionary["merchantid"] = self.merchant_id
        configuration_dictionary["run_environment"] = self.run_environment
        configuration_dictionary["request_json_path"] = ""
        configuration_dictionary["key_alias"] = self.merchant_id
        configuration_dictionary["key_password"] = self.merchant_id
        configuration_dictionary["key_file_name"] = self.merchant_id
        configuration_dictionary["keys_directory"] = self.keys_directory
        configuration_dictionary["merchant_keyid"] = self.merchant_key_id
        configuration_dictionary["merchant_secretkey"] = self.merchant_secret_key
        configuration_dictionary["use_metakey"] = self.use_metakey
        configuration_dictionary["portfolio_id"] = self.portfolio_id
        configuration_dictionary["timeout"] = self.timeout
        configuration_dictionary["defaultDeveloperId"] = self.default_developer_id
        configuration_dictionary["jwePEMFileDirectory"] = self.jwe_pem_file_directory
        configuration_dictionary["useMLEGlobally"] = self.useMLEGlobally

        log_config = LogConfiguration()
        log_config.set_enable_log(self.enable_log)
        log_config.set_log_directory(self.log_directory)
        log_config.set_log_file_name(self.log_file_name)
        log_config.set_log_maximum_size(self.log_maximum_size)
        log_config.set_log_level(self.log_level)
        log_config.set_enable_masking(self.enable_masking)
        log_config.set_log_format(self.log_format)
        log_config.set_log_date_format(self.log_date_format)
        configuration_dictionary["log_config"] = log_config

        return configuration_dictionary
