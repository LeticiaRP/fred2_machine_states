#!/usr/bin/env python3

import rclpy
import threading
import yaml
import sys
import os

from typing import List
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from std_msgs.msg import Bool, Int16


# Parameters file (yaml)
node_path = '~/ros2_ws/src/fred2_machine_states/config/params.yaml'
node_group = 'goal_mode'


debug_mode = '--debug' in sys.argv


class Fred_state(Node):

    def __init__(self,
                 node_name: str,
                 *,
                 context:
                 Context = None,
                 cli_args: List[str] = None,
                 namespace: str = None,
                 use_global_arguments: bool = True,
                 enable_rosout: bool = True,
                 start_parameter_services: bool = True,
                 parameter_overrides: List[Parameter] = None,
                 allow_undeclared_parameters: bool = False,
                 automatically_declare_parameters_from_overrides: bool = False) -> None:


        super().__init__(node_name,
                         context=context,
                         cli_args=cli_args,
                         namespace=namespace,
                         use_global_arguments=use_global_arguments,
                         enable_rosout=enable_rosout,
                         start_parameter_services=start_parameter_services,
                         parameter_overrides=parameter_overrides,
                         allow_undeclared_parameters=allow_undeclared_parameters,
                         automatically_declare_parameters_from_overrides=automatically_declare_parameters_from_overrides)

        # robot mode (MANUAL | AUTONOMOUS)  # robot state (EMERGENCY | IN GOAL | MISSION COMPLETED | MANUAL | AUTONOMOUS)
        self.robot_state = 2    # Starts in EMERGENCY state 
        self.robot_mode = 0     # Starts in MANUAL mode 

        self.last_change_mode = False
        self.switch_mode = False

        self.joy_connected = False      # For safety, assume that the joy isn't connected 

        self.collision_alert = False
        self.abort_command = True       # For safety the robot, the user must unlock the robot

        self.completed_course = False
        self.goal_reached = False

        self.reset_robot_state = False

        self.robot_state_msg = Int16()


        self.load_params(node_path, node_group)
        self.get_params()



        self.create_subscription(Bool,
                                 '/joy/machine_states/switch_mode',
                                 self.switchMode_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/joy/controler/connected',
                                 self.joyConnectec_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/safety/abort/user_command',
                                 self.abortCommand_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/safety/abort/collision_alert',
                                 self.collisionDetection_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/goal_manager/goal/mission_completed',
                                 self.missionCompleted_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/goal_manager/goal/reached',
                                 self.goalReached_callback,
                                 1)


        self.create_subscription(Bool,
                                 '/odom/reset',
                                 self.reset_callback,
                                 1)


        self.robotState_pub = self.create_publisher(Int16, 'robot_state', 10)


    def reset_callback(self, reset):
        
        self.reset_robot_state = reset.data



    def goalReached_callback(self, goal):
        
        self.goal_reached = goal.data



    def missionCompleted_callback(self, mission_completed):
        
        self.completed_course = mission_completed.data




    def collisionDetection_callback(self, collision):
        
        self.collision_alert = collision.data




    def abortCommand_callback(self, abort):
        
        self.abort_command = abort.data




    def joyConnectec_callback(self, joy_status):
        
        self.joy_connected = joy_status.data





    def switchMode_callback(self, change_mode):
        

        if change_mode.data > self.last_change_mode:


            if self.robot_mode == self.MANUAL: 

                self.robot_mode = self.AUTONOMOUS



            elif self.robot_mode == self.AUTONOMOUS: 

                self.robot_mode = self.MANUAL         

        

        self.last_change_mode = change_mode.data




    def machine_states(self):
        

        if not(self.joy_connected) or self.abort_command or self.collision_alert:

            self.robot_state = self.EMERGENCY


        else: 
            

            if self.robot_mode == self.AUTONOMOUS: 
                
                self.robot_state = self.AUTONOMOUS



                if self.goal_reached: 
                    
                    self.robot_state = self.IN_GOAL

                
                if self.completed_course: 
                    
                    self.robot_state = self.MISSION_COMPLETED
            


            elif self.robot_mode == self.MANUAL: 
                
                self.robot_state = self.MANUAL
            
            

            if self.reset_robot_state: 
                                
                self.robot_mode = self.MANUAL


        self.robot_state_msg.data = self.robot_state
        self.robotState_pub.publish(self.robot_state_msg)


        if debug_mode: 
            
            self.get_logger().info(f"Robot State: {self.robot_state_msg}\n")
            self.get_logger().info(f"\nGoal Reached: {self.goal_reached} | Mission Completed: {self.completed_course} | Reset: {self.reset_robot_state} | Joy connected: {self.joy_connected} | Abort: {self.abort_command} | Collision: {self.collision_alert}")

        
        
    def load_params(self, path, group):
        param_path = os.path.expanduser(path)

        with open(param_path, 'r') as params_list:
            params = yaml.safe_load(params_list)

        # Get the params inside the specified group
        params = params.get(group, {})

        # Declare parameters with values from the YAML file
        for param_name, param_value in params.items():
            # Adjust parameter name to lowercase
            param_name_lower = param_name.lower()
            self.declare_parameter(param_name_lower, param_value)
            self.get_logger().info(f'{param_name_lower}: {param_value}')



    def get_params(self):
        self.MANUAL = self.get_parameter('manual').value
        self.AUTONOMOUS = self.get_parameter('autonomous').value
        self.IN_GOAL = self.get_parameter('in_goal').value
        self.MISSION_COMPLETED = self.get_parameter('mission_completed').value
        self.EMERGENCY = self.get_parameter('emergency').value



if __name__ == '__main__':
    rclpy.init()

    # Create a custom context for single thread and real-time execution
    states_context = rclpy.Context()
    states_context.init()
    states_context.use_real_time = True

    node = Fred_state(
        node_name='goal_mode',
        cli_args='--debug',
        context=states_context,
        namespace='machine_states',
        start_parameter_services=True
    )

    # Make the execution in real time
    executor = SingleThreadedExecutor(context=states_context)
    executor.add_node(node=node)

    # Separate thread for callbacks
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()

    rate = node.create_rate(1)

    try:
        while rclpy.ok():
            node.machine_states()
            rate.sleep()

    except KeyboardInterrupt:
        pass

    rclpy.shutdown()
    thread.join()
