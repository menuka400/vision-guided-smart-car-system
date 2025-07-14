"""
Simple Smart Car Controller with Hand Gesture Control
- Responds to hand gestures (left hand = forward, right hand = stop)
- 2-second cooldown between commands to prevent ESP32 overload
- Immediate stop when hand gesture ends
"""

import requests
import time
import logging

logger = logging.getLogger(__name__)

class SmartCarController:
    def __init__(self, car_ip: str = "192.168.1.112", car_port: int = 80):
        """
        Initialize the smart car controller
        
        Args:
            car_ip: IP address of the smart car
            car_port: Port number of the smart car web server
        """
        self.car_ip = car_ip
        self.car_port = car_port
        self.base_url = f"http://{car_ip}:{car_port}"
        self.last_gesture = None
        self.last_command_time = time.time()
        self.min_command_interval = 2.0  # 2 second cooldown between commands
        self.command_in_progress = False
        self.was_moving = False  # Track if the car was moving
        
    def send_hand_gesture(self, gesture: str, force: bool = False) -> bool:
        """
        Send hand gesture command to the smart car
        
        Args:
            gesture: The gesture command to send
            force: If True, bypasses the cooldown check (used for stop commands)
        """
        current_time = time.time()
        
        # Check if enough time has passed since last command, unless forced
        if not force:
            time_since_last = current_time - self.last_command_time
            if time_since_last < self.min_command_interval:
                # If the gesture is the same as last time, just return success
                if gesture == self.last_gesture:
                    return True
                # If it's a new gesture but cooldown isn't finished, ignore it
                logger.info(f"Command cooldown: {self.min_command_interval - time_since_last:.1f}s remaining")
                return False
            
        # Don't send the same command twice unless forced
        if gesture == self.last_gesture and not force:
            return True
            
        try:
            # Set command in progress flag
            self.command_in_progress = True
            
            url = f"{self.base_url}/hand-gesture"
            data = {"gesture": gesture}
            
            response = requests.post(url, data=data, timeout=2)
            
            if response.status_code == 200:
                logger.info(f"Successfully sent gesture command: {gesture}")
                self.last_gesture = gesture
                # Only update command time for non-forced commands
                if not force:
                    self.last_command_time = current_time
                return True
            else:
                logger.error(f"Failed to send gesture command. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending gesture command: {e}")
            return False
        finally:
            # Clear command in progress flag
            self.command_in_progress = False
    
    def handle_gesture(self, has_raised_hand: bool = False, hand_side: str = None) -> bool:
        """Process hand detection results and send appropriate commands to the car"""
        # Don't process new gestures if a command is in progress
        if self.command_in_progress:
            return False
            
        # Check if we need to stop
        is_moving_command = hand_side == "left"
        
        # If we were moving and the hand is now down, send immediate stop
        if self.was_moving and (not has_raised_hand or not is_moving_command):
            logger.info("Movement stopped - sending immediate stop command")
            self.was_moving = False
            return self.send_hand_gesture("none", force=True)
            
        # Handle regular gesture commands with cooldown
        if not has_raised_hand:
            self.was_moving = False
            return self.send_hand_gesture("none")
        
        if hand_side == "left":
            self.was_moving = True
            return self.send_hand_gesture("left")
        elif hand_side == "right":
            self.was_moving = False
            return self.send_hand_gesture("right")
        else:
            self.was_moving = False
            return self.send_hand_gesture("both")
    
    def test_connection(self) -> bool:
        """Test connection to the smart car"""
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
        """Send emergency stop command to the car"""
        logger.warning("Sending emergency stop command")
        self.was_moving = False
        # Emergency stop always bypasses the cooldown
        return self.send_hand_gesture("none", force=True)

def main():
    """Test the car controller functionality"""
    # Initialize the car controller
    car_controller = SmartCarController()
    
    # Test connection
    if not car_controller.test_connection():
        print("Failed to connect to smart car. Please check connection.")
        return
    
    print("Smart Car Controller Test")
    print("Testing hand gesture commands...")
    print("Note: 2-second cooldown between commands (except for stop)")
    
    # Test hand gesture commands
    gesture_commands = [
        ("none", "Stop command"),
        ("left", "Left hand raised - forward"),
        ("none", "Hand lowered - immediate stop"),
        ("left", "Left hand raised - forward"),
        ("right", "Right hand raised - stop"),
        ("none", "No hands - stop")
    ]
    
    for command, description in gesture_commands:
        print(f"\nTesting: {description}")
        success = car_controller.send_hand_gesture(command)
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        time.sleep(3)  # Wait longer than cooldown to ensure commands go through

if __name__ == "__main__":
    main()
