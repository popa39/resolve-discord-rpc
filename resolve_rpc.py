#!/usr/bin/env python3
"""
DaVinci Resolve Discord Rich Presence for Linux
Runs inside DaVinci Resolve via Console
"""

import time
import sys
sys.path.append("/opt/resolve/Developer/Scripting/Modules/")
import atexit
import signal
from pypresence import Presence
import DaVinciResolveScript as dvr_script

# Discord Application ID (create your app at https://discord.com/developers/applications)
CLIENT_ID = "1257700837833179136"

# Page to icon mapping (upload them to Discord Developer Portal)
PAGE_IMAGES = {
    "media": "media_icon",
    "cut": "cut_icon", 
    "edit": "edit_icon",
    "fusion": "fusion_icon",
    "color": "color_icon",
    "fairlight": "fairlight_icon",
    "deliver": "deliver_icon",
    "render": "render_icon"  # Add render icon
}

PAGE_NAMES = {
    "media": "Media",
    "cut": "Cut",
    "edit": "Edit",
    "fusion": "Fusion",
    "color": "Color",
    "fairlight": "Fairlight",
    "deliver": "Deliver"
}

class ResolveRPC:
    def __init__(self):
        self.rpc = None
        self.resolve = None
        self.project_manager = None
        self.project = None
        self.timeline = None
        self.last_state = {}
        self.start_time = time.time()
        self.is_running = False
        self.is_rendering = False
        self.render_start_time = None
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle termination signals"""
        print("\n\n✓ Received termination signal...")
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clear Discord status on exit"""
        if self.rpc and self.is_running:
            try:
                print("✓ Clearing Discord status...")
                self.rpc.clear()
                time.sleep(0.5)  # Give time to process
                self.rpc.close()
                print("✓ Disconnected from Discord")
            except Exception as e:
                print(f"⚠ Error during cleanup: {e}")
            finally:
                self.is_running = False
        
    def connect_discord(self):
        """Connect to Discord RPC"""
        try:
            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()
            self.is_running = True
            print("✓ Connected to Discord")
            return True
        except Exception as e:
            print(f"✗ Discord connection error: {e}")
            return False
    
    def connect_resolve(self):
        """Connect to DaVinci Resolve API"""
        try:
            self.resolve = dvr_script.scriptapp("Resolve")
            if not self.resolve:
                print("✗ Could not connect to Resolve")
                return False
            
            self.project_manager = self.resolve.GetProjectManager()
            self.project = self.project_manager.GetCurrentProject()
            
            if not self.project:
                print("✗ No open project")
                return False
                
            print("✓ Connected to DaVinci Resolve")
            return True
        except Exception as e:
            print(f"✗ Resolve connection error: {e}")
            return False
    
    def get_current_page(self):
        """Get currently open page"""
        try:
            return self.resolve.GetCurrentPage().lower()
        except:
            return "edit"
    
    def get_timeline_info(self):
        """Get timeline information"""
        try:
            self.timeline = self.project.GetCurrentTimeline()
            if self.timeline:
                return {
                    "name": self.timeline.GetName(),
                    "fps": self.timeline.GetSetting("timelineFrameRate")
                }
        except:
            pass
        return None
    
    def check_render_status(self):
        """Check render status"""
        try:
            # Get render status
            render_status = self.project.IsRenderingInProgress()
            
            if render_status and not self.is_rendering:
                # Render just started
                self.is_rendering = True
                self.render_start_time = time.time()
                print("Render started!")
                
            elif not render_status and self.is_rendering:
                # Render just finished
                self.is_rendering = False
                self.render_start_time = None
                print("✓ Render completed!")
            
            return render_status
            
        except Exception as e:
            return False
    
    def get_render_progress(self):
        """Get render progress"""
        try:
            # Get current render job
            render_jobs = self.project.GetRenderJobList()
            
            if render_jobs:
                # Take the latest job
                for job in render_jobs:
                    job_info = self.project.GetRenderJobStatus(job["JobId"])
                    
                    if job_info and job_info.get("JobStatus") == "Rendering":
                        completion = job_info.get("CompletionPercentage", 0)
                        
                        return {
                            "percentage": int(completion),
                            "job_name": job.get("TargetDir", "Unknown"),
                            "status": job_info.get("JobStatus", "Unknown")
                        }
            
            return None
            
        except Exception as e:
            print(f"⚠ Error getting progress: {e}")
            return None
    
    def check_resolve_alive(self):
        """Check if Resolve is still running"""
        try:
            # Try to get current project
            self.project = self.project_manager.GetCurrentProject()
            return self.project is not None
        except:
            return False
    
    def update_presence(self):
        """Update Discord status"""
        try:
            # Check if Resolve is still running
            if not self.check_resolve_alive():
                print("✗ Resolve closed or project closed")
                self.cleanup()
                return False
            
            # Check render status
            is_rendering = self.check_render_status()
            
            # Form base data
            project_name = self.project.GetName()
            
            if is_rendering:
                # Render mode
                render_info = self.get_render_progress()
                
                state_data = {
                    "details": f"Project: {project_name}",
                    "large_image": "resolve_logo",
                    "large_text": "DaVinci Resolve",
                }
                
                if render_info and render_info["percentage"] > 0:
                    percentage = render_info["percentage"]
                    state_data["state"] = f"Rendering: {percentage}% complete"
                    
                    # Show progress bar in percentages
                    # Discord supports time display
                    if self.render_start_time:
                        state_data["start"] = int(self.render_start_time)
                    
                    # Render icon
                    state_data["small_image"] = PAGE_IMAGES.get("render", "deliver_icon")
                    state_data["small_text"] = f"Rendering {percentage}%"
                    
                    print(f"🎬 Render: {percentage}%")
                else:
                    state_data["state"] = "Rendering in progress..."
                    state_data["small_image"] = PAGE_IMAGES.get("render", "deliver_icon")
                    state_data["small_text"] = "Rendering"
                    
                    if self.render_start_time:
                        state_data["start"] = int(self.render_start_time)
                
            else:
                # Normal mode
                page = self.get_current_page()
                timeline_info = self.get_timeline_info()
                
                state_data = {
                    "details": f"Project: {project_name}",
                    "large_image": "resolve_logo",
                    "large_text": "DaVinci Resolve",
                    "start": int(self.start_time)
                }
                
                # Add current page info
                if page in PAGE_IMAGES:
                    state_data["small_image"] = PAGE_IMAGES[page]
                    state_data["small_text"] = PAGE_NAMES[page]
                    state_data["state"] = f"{PAGE_NAMES[page]}"
                
                # Add timeline info
                if timeline_info:
                    timeline_text = f"Timeline: {timeline_info['name']}"
                    if "state" in state_data:
                        state_data["state"] += f" | {timeline_text}"
                    else:
                        state_data["state"] = timeline_text
            
            # Update only if changed
            if state_data != self.last_state:
                self.rpc.update(**state_data)
                self.last_state = state_data
                
                if not is_rendering:
                    page = self.get_current_page()
                    print(f"↻ Updated: {PAGE_NAMES.get(page, page)}")
            
            return True
                
        except Exception as e:
            print(f"✗ Update error: {e}")
            return False
    
    def run(self):
        """Main loop"""
        print("=== DaVinci Resolve Discord RPC for Linux ===\n")
        
        if not self.connect_discord():
            return
        
        if not self.connect_resolve():
            self.cleanup()
            return
        
        print("\n✓ All systems running!")
        print("Updating every 3 seconds. Press Ctrl+C to stop.\n")
        
        try:
            while self.is_running:
                if not self.update_presence():
                    break
                # More frequent updates for render tracking
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n\n✓ Stopping...")
        except Exception as e:
            print(f"\n✗ Critical error: {e}")
        finally:
            self.cleanup()

def main():
    rpc = ResolveRPC()
    rpc.run()

if __name__ == "__main__":
    main()
