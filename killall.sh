#!/usr/bin/env bash
# killall.sh — kill all robonix-related processes on this host.
#
# 覆盖:
#   - rbnx boot 监督者 + rust 二进制 (atlas/executor/pilot/liaison/codegen)
#   - system/* python 模块 (scene/voiceprint/memsearch/speech/welcome)
#   - skill/service wrappers (explore/mapping/nav2)
#   - primitive node mains (mid360/realsense/ranger/audio/piper)
#   - ros2 launch 派生的子节点 (nav2 stack, rtabmap, RSP, static_tf,
#     realsense2_camera, livox_ros_driver2 等)
#   - 我之前 ssh manual test 留下的 uv run / bash -lc 孤儿
#
# 不杀:
#   - ros2 daemon (无害,下次 ros2 命令会复用)
#   - VS Code server、blueman、jtop 等系统 / 桌面进程
#
# Safe to run anytime (no-op if nothing matches). 先 SIGTERM 2s 给清理
# 机会,然后 SIGKILL。
set +e

PATTERNS=(
    # rbnx supervisor + rust binaries
    'rbnx boot'
    'robonix-atlas'
    'robonix-executor'
    'robonix-pilot'
    'robonix-liaison'
    'robonix-codegen'

    # system/ python services
    'scene_service\.service'
    'voiceprint_service\.service'
    'memsearch_service\.service'
    'speech_service\.service'

    # skill / service atlas bridges
    'welcome_skill\.atlas_bridge'
    'explore_skill\.atlas_bridge'
    'mapping_rbnx\.atlas_bridge'
    'nav2_wrapper\.atlas_bridge'
    'pick_skill\.atlas_bridge'

    # primitive node mains
    'mid360_driver\.main'
    'mid360_imu\.main'
    'realsense_camera\.main'
    'ranger_chassis\.main'
    'audio_driver\.main'
    'audio_macos_bridge\.main'
    'piper_ctl\.main'
    'orbbec_camera\.main'

    # ros2 launch children (often outlive their parent on SIGINT)
    'ros2 launch'
    'rtabmap_slam'
    '/rtabmap '
    'icp_odometry'
    'rtabmap_viz'
    'controller_server'
    'planner_server'
    'bt_navigator'
    'behavior_server'
    'smoother_server'
    'lifecycle_manager'
    'static_transform_publisher'
    'robot_state_publisher'
    'realsense2_camera_node'
    'livox_ros_driver'
    'piper_single_ctrl'
    'move_group'
    'tf_to_pose\.py'
    'yolo_world_node'
    'yolo_grasp_node'

    # 孤儿 wrappers (我 manual test 留下的)
    'uv run --active python'
)

echo "[killall] SIGTERM round …"
for p in "${PATTERNS[@]}"; do
    pkill -TERM -f "$p" 2>/dev/null
done
sleep 2

echo "[killall] SIGKILL round …"
for p in "${PATTERNS[@]}"; do
    pkill -9 -f "$p" 2>/dev/null
done
sleep 1

echo
echo "[killall] survivors (应为空,VS Code / jtop / blueman 等系统进程不在列表里):"
ps -ef | grep -E 'robonix-|rbnx boot|scene_service|voiceprint_service|memsearch_service|speech_service|welcome_skill|explore_skill|nav2_wrapper|mapping_rbnx|mid360_(driver|imu)|realsense_camera\.|ranger_chassis\.|audio_driver\.|audio_macos_bridge\.|piper_ctl\.|orbbec_camera\.|rtabmap|controller_server|planner_server|bt_navigator|behavior_server|smoother_server|lifecycle_manager|static_transform_publisher|robot_state_publisher|realsense2_camera_node|livox_ros_driver|piper_single|move_group|tf_to_pose|yolo_world_node|yolo_grasp_node' \
    | grep -v 'grep ' | grep -v "$0" | head -20

echo
echo "[killall] listening robonix ports (50051/50061/50071/50081/50107 应该全空):"
ss -tlnp 2>/dev/null | grep -E ':(5005[0-9]|5006[0-9]|5007[0-9]|5008[0-9]|50107)\b' | head

echo
echo "[killall] done."
