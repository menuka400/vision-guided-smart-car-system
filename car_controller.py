"""
Enhanced Smart Car Controller with Person Tracking and Orientation Adjustment
"""

import requests
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class SmartCarController:
    def __init__(self, car_ip: str = "192.168.4.1", car_port: int = 80):
        """
        Initialize the smart car controller with tracking capabilities
        
        Args:
            car_ip: IP address of the smart car
            car_port: Port number of the smart car web server
        """
        self.car_ip = car_ip
        self.car_port = car_port
        self.base_url = f"http://{car_ip}:{car_port}"
        self.last_gesture = None
        self.last_tracking_action = None
        self.last_command_time = time.time()
        self.min_command_interval = 0.1  # Minimum time between commands (100ms)
        
        # Tracking parameters
        self.frame_center_threshold = 50  # Pixels from center to consider "centered"
        self.tracking_enabled = True
        self.last_person_position = None
        
    def send_hand_gesture(self, gesture: str) -> bool:
        """Send hand gesture command to the smart car"""
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
    
    def send_tracking_command(self, action: str) -> bool:
        """
        Send person tracking command to adjust car orientation
        
        Args:
            action: Tracking action ('track_left', 'track_right', 'track_center')
            
        Returns:
            bool: True if command was sent successfully
        """
        current_time = time.time()
        
        # Avoid sending duplicate tracking commands too frequently
        if (action == self.last_tracking_action and 
            current_time - self.last_command_time < self.min_command_interval):
            return True
            
        try:
            url = f"{self.base_url}/person-tracking"
            data = {"action": action}
            
            response = requests.post(url, data=data, timeout=2)
            
            if response.status_code == 200:
                logger.info(f"Successfully sent tracking command: {action}")
                self.last_tracking_action = action
                self.last_command_time = current_time
                return True
            else:
                logger.error(f"Failed to send tracking command. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending tracking command: {e}")
            return False
    
    def calculate_tracking_adjustment(self, person_center: Tuple[int, int], frame_dimensions: Tuple[int, int]) -> str:
        """
        Calculate required car orientation adjustment based on person position
        
        Args:
            person_center: (x, y) coordinates of person center
            frame_dimensions: (width, height) of the frame
            
        Returns:
            str: Required tracking action ('track_left', 'track_right', 'track_center')
        """
        if not self.tracking_enabled:
            return 'track_center'
            
        frame_width, frame_height = frame_dimensions
        frame_center_x = frame_width // 2
        person_x, person_y = person_center
        
        # Calculate horizontal offset from center
        offset_x = person_x - frame_center_x
        
        # Determine required adjustment
        if offset_x < -self.frame_center_threshold:
            # Person is to the left, car should turn left to center them
            return 'track_left'
        elif offset_x > self.frame_center_threshold:
            # Person is to the right, car should turn right to center them
            return 'track_right'
        else:
            # Person is centered, no adjustment needed
            return 'track_center'
    
    def handle_person_tracking(self, person_center: Optional[Tuple[int, int]], 
                             frame_dimensions: Tuple[int, int], 
                             has_raised_hand: bool = False, 
                             hand_side: Optional[str] = None) -> bool:
        """
        Handle person tracking with both hand gesture and orientation adjustment
        
        Args:
            person_center: (x, y) coordinates of tracked person center
            frame_dimensions: (width, height) of the frame
            has_raised_hand: Whether person has raised hand
            hand_side: Which hand is raised
            
        Returns:
            bool: True if commands were processed successfully
        """
        success = True
        
        # Handle hand gesture commands first
        if has_raised_hand:
            gesture_success = self.handle_raised_hand_detection(has_raised_hand, hand_side)
            success = success and gesture_success
        else:
            # No hand raised, send stop command
            gesture_success = self.send_hand_gesture("none")
            success = success and gesture_success
        
        # Handle car orientation adjustment for tracking
        if person_center is not None:
            tracking_action = self.calculate_tracking_adjustment(person_center, frame_dimensions)
            tracking_success = self.send_tracking_command(tracking_action)
            success = success and tracking_success
            
            self.last_person_position = person_center
            
            # Log tracking adjustment
            if tracking_action != 'track_center':
                logger.info(f"Person at {person_center}, adjusting car orientation: {tracking_action}")
        else:
            # No person detected, stop tracking adjustment
            tracking_success = self.send_tracking_command('track_center')
            success = success and tracking_success
            self.last_person_position = None
        
        return success
    
    def handle_raised_hand_detection(self, has_raised_hand: bool, hand_side: Optional[str] = None) -> bool:
        """Process hand detection results and send appropriate commands to the car"""
        if not has_raised_hand:
            return self.send_hand_gesture("none")
        
        if hand_side == "left":
            return self.send_hand_gesture("left")
        elif hand_side == "right":
            return self.send_hand_gesture("right")
        else:
            return self.send_hand_gesture("both")
    
    def set_tracking_sensitivity(self, threshold: int):
        """
        Adjust tracking sensitivity
        
        Args:
            threshold: Pixel threshold for considering person "centered"
        """
        self.frame_center_threshold = threshold
        logger.info(f"Tracking sensitivity set to {threshold} pixels")
    
    def enable_tracking(self, enabled: bool):
        """Enable or disable person tracking"""
        self.tracking_enabled = enabled
        logger.info(f"Person tracking {'enabled' if enabled else 'disabled'}")
        
        if not enabled:
            # Send center command to stop any ongoing tracking movement
            self.send_tracking_command('track_center')
    
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
        success1 = self.send_hand_gesture("none")
        success2 = self.send_tracking_command("track_center")
        return success1 and success2


def main():
    """Test the enhanced car controller functionality"""
    # Initialize the car controller
    car_controller = SmartCarController()
    
    # Test connection
    if not car_controller.test_connection():
        print("Failed to connect to smart car. Please check connection.")
        return
    
    print("Enhanced Smart Car Controller Test")
    print("Testing tracking commands...")
    
    # Test tracking commands
    tracking_commands = [
        ("track_center", "Center position - no movement"),
        ("track_left", "Turn left to track person"),
        ("track_right", "Turn right to track person"),
        ("track_center", "Return to center")
    ]
    
    for command, description in tracking_commands:
        print(f"\nTesting: {description}")
        success = car_controller.send_tracking_command(command)
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        time.sleep(2)
    
    # Test combined tracking
    print("\nTesting combined person tracking...")
    frame_dims = (640, 480)
    
    # Simulate person at different positions
    positions = [
        ((320, 240), "Center position"),
        ((100, 240), "Left side - should turn left"),
        ((540, 240), "Right side - should turn right"),
        ((320, 240), "Back to center")
    ]
    
    for position, description in positions:
        print(f"\nSimulating: {description}")
        success = car_controller.handle_person_tracking(
            person_center=position,
            frame_dimensions=frame_dims,
            has_raised_hand=False
        )
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
        time.sleep(2)
    
    # Final stop
    car_controller.emergency_stop()
    print("\nTest completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
