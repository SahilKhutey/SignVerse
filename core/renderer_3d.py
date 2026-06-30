import numpy as np
import plotly.graph_objects as go
from typing import List, Dict, Any, Optional, Tuple

class Skeleton3DRenderer:
    """Renders real-time 3D skeleton models using Plotly Scatter3d graphics"""
    
    # MediaPipe pose connections (from/to indices)
    BONES = [
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # arms/shoulders
        (11, 23), (12, 24), (23, 24),                       # collar/torso
        (23, 25), (25, 27), (24, 26), (26, 28),             # legs
        (27, 29), (27, 31), (28, 30), (28, 32),             # feet
        (11, 12)                                            # shoulder line closure
    ]
    
    HAND_BONES = [
        (0, 1), (1, 2), (2, 3), (3, 4),                     # thumb
        (0, 5), (5, 6), (6, 7), (7, 8),                     # index
        (0, 9), (9, 10), (10, 11), (11, 12),                # middle
        (0, 13), (13, 14), (14, 15), (15, 16),              # ring
        (0, 17), (17, 18), (18, 19), (19, 20),              # pinky
        (5, 9), (9, 13), (13, 17)                           # palm baseline joints
    ]
    
    def render_frame_3d(self, frame_data: Dict[str, Any]) -> go.Figure:
        """Generates a 3D scatter plot of the body skeleton, hands, and face mesh"""
        fig = go.Figure()
        
        # 1. Pose Skeleton Lines (Body)
        pose_lms = frame_data.get('landmarks_33', [])
        if pose_lms and len(pose_lms) >= 33:
            self._add_skeleton_trace(fig, pose_lms, self.BONES, 
                                     color='#00D9FF', name='Body Skeleton')
            
        # 2. Hand Skeleton Lines (Left and Right)
        left_hand = frame_data.get('left_hand_21', [])
        if left_hand and len(left_hand) >= 21:
            self._add_skeleton_trace(fig, left_hand, self.HAND_BONES,
                                     color='#FF0055', name='Left Hand')
                                     
        right_hand = frame_data.get('right_hand_21', [])
        if right_hand and len(right_hand) >= 21:
            self._add_skeleton_trace(fig, right_hand, self.HAND_BONES,
                                     color='#00FF66', name='Right Hand')
            
        # 3. Face Mesh Landmarks (Markers only, for lightweight expressiveness)
        face_mesh = frame_data.get('face_mesh', [])
        if face_mesh:
            # Flip Y axis coordinate to display upright
            fx = [lm['x'] for lm in face_mesh]
            fy = [-lm['y'] for lm in face_mesh]
            fz = [lm['z'] for lm in face_mesh]
            
            fig.add_trace(go.Scatter3d(
                x=fx, y=fy, z=fz,
                mode='markers',
                marker=dict(
                    size=1.5, 
                    color='#FFD700', 
                    opacity=0.7
                ),
                name='Face Mesh',
                hoverinfo='skip'
            ))
            
        # Layout styling with dark theme matching premium UI design
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            scene=dict(
                xaxis=dict(
                    title='X (Lateral)',
                    backgroundcolor='rgba(0,0,0,0)',
                    gridcolor='rgba(255,255,255,0.05)',
                    showbackground=False,
                    zerolinecolor='rgba(255,255,255,0.1)'
                ),
                yaxis=dict(
                    title='Y (Vertical)',
                    backgroundcolor='rgba(0,0,0,0)',
                    gridcolor='rgba(255,255,255,0.05)',
                    showbackground=False,
                    zerolinecolor='rgba(255,255,255,0.1)'
                ),
                zaxis=dict(
                    title='Z (Depth)',
                    backgroundcolor='rgba(0,0,0,0)',
                    gridcolor='rgba(255,255,255,0.05)',
                    showbackground=False,
                    zerolinecolor='rgba(255,255,255,0.1)'
                ),
                aspectmode='cube',
                camera=dict(
                    eye=dict(x=0.0, y=1.2, z=1.8),  # optimal angle showing full model upright
                    up=dict(x=0, y=1, z=0)
                )
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            height=600,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(0,0,0,0.5)"
            )
        )
        return fig
        
    def _add_skeleton_trace(self, fig: go.Figure, landmarks: List[Dict[str, float]], bones: List[Tuple[int, int]], color: str, name: str):
        """Constructs a single Plotly trace with None separators to optimize rendering speed"""
        x_coords = []
        y_coords = []
        z_coords = []
        
        # Build coordinates
        for start, end in bones:
            if start < len(landmarks) and end < len(landmarks):
                # Fetch positions
                p_start = landmarks[start]
                p_end = landmarks[end]
                
                # Append line segment (with y coordinate flipped to project upright)
                x_coords.extend([p_start['x'], p_end['x'], None])
                y_coords.extend([-p_start['y'], -p_end['y'], None])
                z_coords.extend([p_start['z'], p_end['z'], None])
                
        # Draw joint nodes
        jx = [lm['x'] for lm in landmarks]
        jy = [-lm['y'] for lm in landmarks]
        jz = [lm['z'] for lm in landmarks]
        
        # Add joints markers
        fig.add_trace(go.Scatter3d(
            x=jx, y=jy, z=jz,
            mode='markers',
            marker=dict(size=3.5, color=color),
            name=f"{name} Joints",
            hoverinfo='skip'
        ))
        
        # Add connection lines as a single unified trace
        fig.add_trace(go.Scatter3d(
            x=x_coords, y=y_coords, z=z_coords,
            mode='lines',
            line=dict(color=color, width=3.5),
            name=name,
            showlegend=False,
            hoverinfo='skip'
        ))
