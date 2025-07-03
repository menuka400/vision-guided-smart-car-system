"""
Smart Car Controller for Hand Gesture Integration
This module handles communication between the hand detection system and the smart car
"""

import requests
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SmartCarController:
    def __init__(self, car_ip: str = "192.168.4.1", car_port: int = 80):
        """
        Initialize the smart car controller
        
        Args:
            car_ip: IP address of the smart car (default is ESP32 AP mode IP)
            car_port: Port number of the smart car web server
        """
        self.car_ip = car_ip
        self.car_port = car_port
        self.base_url = f"http://{car_ip}:{car_port}"
        self.last_gesture = None
        self.last_command_time = time.time()
        self.min_command_interval = 0.1  # Minimum time between commands (100ms)
        
    def send_hand_gesture(self, gesture: str) -> bool:
        """
        Send hand gesture command to the smart car
        
        Args:
            gesture: Hand gesture type ('left', 'right', 'both', 'none')
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        current_time = time.time()
        
        # Avoid sending duplicate commands too frequently
        if (gesture == self.last_gesture and 
            current_time - self.last_command_time < self.min_command_interval):
            return True
            
        try:
            url = f"{self.base_url}/hand-gesture"
            data = {"gesture": gesture}
            
            response = requests.post(url, data=data, timeout=2)
            
            if response.status_code == 200:
                logger.info(f"Successfully sent gesture command: {gesture}")
                self.last_gesture = gesture
                self.last_command_time = current_time
                return True
            else:
                logger.error(f"Failed to send gesture command. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending gesture command: {e}")
            return False
    
    def handle_raised_hand_detection(self, has_raised_hand: bool, hand_side: Optional[str] = None) -> bool:
        """
        Process hand detection results and send appropriate commands to the car
        
        Args:
            has_raised_hand: Whether a raised hand is detected
            hand_side: Which hand is raised ('left', 'right', or None)
            
        Returns:
            bool: True if command was processed successfully
        """
        if not has_raised_hand:
            # No hands raised - stop the car
            return self.send_hand_gesture("none")
        
        if hand_side == "left":
            # Left hand raised - move forward
            return self.send_hand_gesture("left")
        elif hand_side == "right":
            # Right hand raised - stop
            return self.send_hand_gesture("right")
        else:
            # Both hands or unclear - stop for safety
            return self.send_hand_gesture("both")
    
    def test_connection(self) -> bool:
        """
        Test connection to the smart car
        
        Returns:
            bool: True if car is reachable, False otherwise
        """
        try:
            response = requests.get(self.base_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Successfully connected to smart car at {self.base_url}")
                return True
            else:
                logger.error(f"Smart car responded with status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to smart car: {e}")
            return False
    
    def emergency_stop(self) -> bool:
        """
        Send emergency stop command to the car
        
        Returns:
            bool: True if stop command was sent successfully
        """
        logger.warning("Sending emergency stop command")
        return self.send_hand_gesture("none")


def main():
    """Test the car controller functionality"""
    # Initialize the car controller
    car_controller = SmartCarController()
    
    # Test connection
    if not car_controller.test_connection():
        print("Failed to connect to smart car. Please check:")
        print("1. Smart car is powered on")
        print("2. WiFi is connected to 'MyWiFiCar' network")
        print("3. Car IP address is correct (default: 192.168.4.1)")
        return
    
    print("Smart car controller test")
    print("Testing hand gesture commands...")
    
    # Test different gestures
    gestures = [
        ("none", "No hands raised - should stop"),
        ("left", "Left hand raised - should move forward"),
        ("right", "Right hand raised - should stop"),
        ("both", "Both hands raised - should stop"),
        ("none", "Final stop command")
    ]
    
    for gesture, description in gestures:
        print(f"\nTesting: {description}")
        success = car_controller.send_hand_gesture(gesture)
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        time.sleep(2)  # Wait 2 seconds between commands
    
    print("\nTest completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
