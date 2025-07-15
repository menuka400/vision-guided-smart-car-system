"""
Configuration loader for Smart Car Vision System
Loads settings from config.yaml file
"""

import yaml
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize configuration loader"""
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Configuration file not found: {self.config_path}")
                return self._get_default_config()
                
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
                logger.info(f"Configuration loaded from {self.config_path}")
                return config
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if file loading fails"""
        return {
            'wifi': {
                'ssid': 'SLT_FIBRE',
                'password': 'abcd1234'
            },
            'car': {
                'ip': '192.168.1.112',
                'port': 80
            },
            'motors': {
                'direction_correction': [-1, 1, 1, 1],
                'max_speed': 255,
                'pwm_frequency': 1000,
                'pwm_resolution': 8,
                'motor2_startup_delay': 50
            },
            'vision': {
                'camera': {
                    'width': 640,
                    'height': 480,
                    'flip_horizontal': True
                },
                'hand_detection': {
                    'confidence_threshold': 0.5,
                    'person_confidence_threshold': 0.5
                },
                'yolo': {
                    'model_file': 'yolo11x-pose.pt',
                    'verbose': False
                }
            },
            'controller': {
                'min_command_interval': 2.0,
                'connection_timeout': 5,
                'request_timeout': 2
            },
            'display': {
                'font_scale': 1,
                'font_thickness': 2,
                'text_color': [0, 255, 0],
                'keypoint_radius': 4,
                'keypoint_color': [255, 0, 0],
                'connection_color': [0, 255, 0],
                'connection_thickness': 2,
                'bbox_color': [0, 255, 0],
                'bbox_thickness': 2
            },
            'logging': {
                'level': 'INFO'
            },
            'system': {
                'enable_motor_tests': False,
                'enable_debug_output': True,
                'enable_car_control': True,
                'emergency_stop_on_exit': True
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('wifi.ssid') returns the WiFi SSID
        """
        try:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
                    
            return value
            
        except Exception as e:
            logger.error(f"Error getting config value for {key_path}: {e}")
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        Example: config.set('wifi.ssid', 'new_network')
        """
        try:
            keys = key_path.split('.')
            current = self.config
            
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Set the final value
            current[keys[-1]] = value
            logger.info(f"Configuration updated: {key_path} = {value}")
            
        except Exception as e:
            logger.error(f"Error setting config value for {key_path}: {e}")
    
    def save(self) -> bool:
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as file:
                yaml.safe_dump(self.config, file, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self.config = self._load_config()
        logger.info("Configuration reloaded")
    
    def get_wifi_config(self) -> Dict[str, str]:
        """Get WiFi configuration"""
        return {
            'ssid': self.get('wifi.ssid', 'SLT_FIBRE'),
            'password': self.get('wifi.password', 'abcd1234')
        }
    
    def get_car_config(self) -> Dict[str, Any]:
        """Get car configuration"""
        return {
            'ip': self.get('car.ip', '192.168.1.112'),
            'port': self.get('car.port', 80)
        }
    
    def get_motor_config(self) -> Dict[str, Any]:
        """Get motor configuration"""
        return {
            'direction_correction': self.get('motors.direction_correction', [-1, 1, 1, 1]),
            'max_speed': self.get('motors.max_speed', 255),
            'pwm_frequency': self.get('motors.pwm_frequency', 1000),
            'pwm_resolution': self.get('motors.pwm_resolution', 8),
            'motor2_startup_delay': self.get('motors.motor2_startup_delay', 50)
        }
    
    def get_vision_config(self) -> Dict[str, Any]:
        """Get vision system configuration"""
        return {
            'camera': {
                'width': self.get('vision.camera.width', 640),
                'height': self.get('vision.camera.height', 480),
                'flip_horizontal': self.get('vision.camera.flip_horizontal', True)
            },
            'hand_detection': {
                'confidence_threshold': self.get('vision.hand_detection.confidence_threshold', 0.5),
                'person_confidence_threshold': self.get('vision.hand_detection.person_confidence_threshold', 0.5)
            },
            'yolo': {
                'model_file': self.get('vision.yolo.model_file', 'yolo11x-pose.pt'),
                'verbose': self.get('vision.yolo.verbose', False)
            }
        }
    
    def get_controller_config(self) -> Dict[str, Any]:
        """Get controller configuration"""
        return {
            'min_command_interval': self.get('controller.min_command_interval', 2.0),
            'connection_timeout': self.get('controller.connection_timeout', 5),
            'request_timeout': self.get('controller.request_timeout', 2)
        }
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration"""
        return {
            'font_scale': self.get('display.font_scale', 1),
            'font_thickness': self.get('display.font_thickness', 2),
            'text_color': tuple(self.get('display.text_color', [0, 255, 0])),
            'keypoint_radius': self.get('display.keypoint_radius', 4),
            'keypoint_color': tuple(self.get('display.keypoint_color', [255, 0, 0])),
            'connection_color': tuple(self.get('display.connection_color', [0, 255, 0])),
            'connection_thickness': self.get('display.connection_thickness', 2),
            'bbox_color': tuple(self.get('display.bbox_color', [0, 255, 0])),
            'bbox_thickness': self.get('display.bbox_thickness', 2)
        }

# Global configuration instance
config = ConfigLoader()
