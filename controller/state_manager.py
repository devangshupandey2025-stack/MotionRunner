from utils.config import AppConfig
from controller.motion_event import MotionEvent

class StateManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.game_lane = config.lane_count // 2  # Start in the center lane
        self.physical_lane = -1

    def process_event(self, event: MotionEvent):
        # Returns a tuple of (previous_game_lane, desired_game_lane) if a lane change is needed
        if event.type == "lane_changed":
            self.physical_lane = event.current
            
            if self.physical_lane == -1:
                # Lost tracking, don't change game lane
                return None
                
            desired_game_lane = self.physical_lane
            
            if desired_game_lane != self.game_lane:
                previous_game_lane = self.game_lane
                self.game_lane = desired_game_lane
                return (previous_game_lane, desired_game_lane)
                
        return None
        
    def reset(self):
        self.game_lane = self.config.lane_count // 2
        self.physical_lane = -1
