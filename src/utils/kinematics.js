import * as THREE from 'three';

/**
 * @file kinematics.js
 * @description Provides constants and functions for 3D human pose kinematic analysis.
 * This module includes joint mappings, skeleton definitions, and functions to calculate
 * various anatomical angles from 3D keypoint data.
 */

// --- Joint Names & Skeleton Layout (H36M 17-point custom mapping) ---
// This mapping corresponds to the custom joint names and indices you provided.
export const H36M_JOINT_NAMES = {
    0: 'Pelvis', 1: 'R_Hip', 2: 'R_Knee', 3: 'R_Ankle',
    4: 'L_Hip', 5: 'L_Knee', 6: 'L_Ankle', 7: 'Torso',
    8: 'Neck', 9: 'Head', 10: 'Headtop', 11: 'R_Shoulder',
    12: 'R_Elbow', 13: 'R_wrist', 14: 'L_Shoulder', 15: 'L_Elbow',
    16: 'L_Wrist'
};

// Defines the connections between joints to draw the skeleton.
export const SKELETON_SEGMENTS = {
    'Pelvis_Torso_Head': { color: 'red', links: [[0, 7], [7, 8], [8, 9], [9, 10]] },
    'Right_Arm': { color: 'blue', links: [[8, 11], [11, 12], [12, 13]] },
    'Left_Arm': { color: 'cyan', links: [[8, 14], [14, 15], [15, 16]] },
    'Right_Leg': { color: 'green', links: [[0, 1], [1, 2], [2, 3]] },
    'Left_Leg': { color: 'lime', links: [[0, 4], [4, 5], [5, 6]] }
};

// --- List of All 23 Kinematic Angles for Analysis ---
export const ANGLE_KEYS = [
    "Neck (X-Axis Rotation)", "Neck (Y-Axis Rotation)", "Neck (Z-Axis Rotation)", "Torso-Neck (Vertical)",
    "Waist (X-Axis Rotation)", "Waist (Y-Axis Rotation)", "Waist (Z-Axis Rotation)",
    "R Shoulder (X-Axis Rotation)", "L Shoulder (X-Axis Rotation)",
    "R Shoulder (Y-Axis Rotation)", "L Shoulder (Y-Axis Rotation)",
    "R Shoulder (Z-Axis Rotation)", "L Shoulder (Z-Axis Rotation)",
    "R_Elbow (Bend)", "L_Elbow (Bend)",
    "R Hip (X-Axis Rotation)", "L Hip (X-Axis Rotation)",
    "R Hip (Y-Axis Rotation)", "L Hip (Y-Axis Rotation)",
    "R Hip (Z-Axis Rotation)", "L Hip (Z-Axis Rotation)",
    "R_Knee (Bend)", "L_Knee (Bend)",
];

/**
 * Main kinematics calculation object.
 * Contains all methods for processing 3D keypoints into anatomical angles.
 */
export const kinematics = {
    /**
     * Converts a 3-element array to a THREE.Vector3 object.
     * @param {number[]} p - The input array [x, y, z].
     * @returns {THREE.Vector3} The corresponding vector.
     */
    toVec3: (p) => new THREE.Vector3(p[0], p[1], p[2]),

    /**
     * Calculates the 3D angle at joint B defined by segments AB and CB.
     * @param {number[]} A - 3D coordinates of the first point.
     * @param {number[]} B - 3D coordinates of the vertex (joint).
     * @param {number[]} C - 3D coordinates of the third point.
     * @returns {number} The angle in degrees.
     */
    calculate_3d_angle: function(A, B, C) {
        if (!A || !B || !C) return 0.0; // Add check for undefined points
        const v1 = new THREE.Vector3().subVectors(this.toVec3(A), this.toVec3(B));
        const v2 = new THREE.Vector3().subVectors(this.toVec3(C), this.toVec3(B));
        const denom = v1.length() * v2.length();
        if (denom < 1e-9) return 0.0;
        const cosv = Math.max(-1.0, Math.min(1.0, v1.dot(v2) / denom));
        return (Math.acos(cosv) * 180) / Math.PI;
    },

    /**
     * Calculates the angle of a segment relative to the world vertical (Y-up) axis.
     * @param {number[]} startKp - 3D coordinates of the segment's start point.
     * @param {number[]} endKp - 3D coordinates of the segment's end point.
     * @returns {number} The vertical angle in degrees.
     */
    calculate_vertical_angle: function(startKp, endKp) {
        if (!startKp || !endKp) return 0.0; // Add check for undefined points
        const seg = new THREE.Vector3().subVectors(this.toVec3(endKp), this.toVec3(startKp));
        const norm = seg.length();
        if (norm < 1e-9) return 0.0;
        const vertical = new THREE.Vector3(0.0, 1.0, 0.0);
        const cosv = Math.max(-1.0, Math.min(1.0, seg.dot(vertical) / norm));
        return (Math.acos(cosv) * 180) / Math.PI;
    },

    /**
     * Converts a THREE.Matrix4 rotation matrix to Euler angles.
     * @param {THREE.Matrix4} R - The rotation matrix.
     * @returns {number[]} An array [rx, ry, rz] of Euler angles in degrees.
     */
    rotation_matrix_to_euler_angles: function(R) {
        // YXZ order is common for anatomical frames and matches the reference logic.
        const euler = new THREE.Euler().setFromRotationMatrix(R, 'YXZ');
        const x = euler.x * 180 / Math.PI;
        const y = euler.y * 180 / Math.PI;
        const z = euler.z * 180 / Math.PI;
        return [x, y, z];
    },
    
    /**
     * Computes a local coordinate system (rotation matrix) for a joint.
     * @param {THREE.Vector3} proximal_vec - Vector from joint to its parent/proximal joint.
     * @param {THREE.Vector3} distal_vec - Vector from joint to its child/distal joint.
     * @returns {THREE.Matrix4} The resulting rotation matrix.
     */
    compute_rotation_matrix: function(proximal_vec, distal_vec) {
        if (proximal_vec.lengthSq() < 1e-9 || distal_vec.lengthSq() < 1e-9) {
            return new THREE.Matrix4().identity();
        }
        const mat = new THREE.Matrix4();
        const eye = new THREE.Vector3(0, 0, 0);
        const target = distal_vec.clone();
        const up = proximal_vec.clone();
        mat.lookAt(eye, target, up);
        return new THREE.Matrix4().copy(mat).invert();
    },

    /**
     * Calculates all complex 3D anatomical angles (Shoulders, Hips, Waist, Neck).
     * @param {Array<number[]>} kp - Array of 3D keypoints.
     * @returns {Object} An object mapping angle names to their calculated values.
     */
    calculate_anatomical_angles: function(kp) {
        const angles = {};
        const p = (i) => this.toVec3(kp[i]);

        // --- WAIST/TORSO ROTATION (Joint Center: Torso 7) ---
        if (kp.length > 8) {
            try {
                const proximal_y = p(7).clone().sub(p(0)).normalize();
                const x_axis_ref = p(1).clone().sub(p(4)).normalize(); // R_Hip -> L_Hip
                
                if (proximal_y.lengthSq() > 1e-9 && x_axis_ref.lengthSq() > 1e-9) {
                    const z_axis_local = new THREE.Vector3().crossVectors(proximal_y, x_axis_ref).normalize();
                    const x_axis_local = new THREE.Vector3().crossVectors(proximal_y, z_axis_local).normalize();
                    const R_local = new THREE.Matrix4().makeBasis(x_axis_local, proximal_y, z_axis_local);

                    const torso_y = p(8).clone().sub(p(7)).normalize();
                    if (torso_y.lengthSq() > 1e-9) {
                        const z_axis_torso = new THREE.Vector3().crossVectors(torso_y, x_axis_ref).normalize();
                        const x_axis_torso = new THREE.Vector3().crossVectors(torso_y, z_axis_torso).normalize();
                        const R_torso = new THREE.Matrix4().makeBasis(x_axis_torso, torso_y, z_axis_torso);
                        
                        const R_local_inv = new THREE.Matrix4().copy(R_local).invert();
                        const R_relative = new THREE.Matrix4().multiplyMatrices(R_torso, R_local_inv);
                        
                        const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(R_relative);
                        angles["Waist (X-Axis Rotation)"] = rx.toFixed(1);
                        angles["Waist (Y-Axis Rotation)"] = ry.toFixed(1);
                        angles["Waist (Z-Axis Rotation)"] = rz.toFixed(1);
                    }
                }
            } catch (e) { console.error("Waist calc error", e); }
        }
        
        // --- NECK ROTATION (Joint Center: Neck 8) ---
        if (kp.length > 9) {
            try {
                const proximal = p(7).sub(p(8)); // Torso -> Neck
                const distal = p(9).sub(p(8));   // Neck -> Head
                const Rm = this.compute_rotation_matrix(proximal, distal);
                const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(Rm);
                angles["Neck (X-Axis Rotation)"] = rx.toFixed(1);
                angles["Neck (Y-Axis Rotation)"] = ry.toFixed(1);
                angles["Neck (Z-Axis Rotation)"] = rz.toFixed(1);
            } catch (e) { console.error("Neck calc error", e); }
        }

        // --- SHOULDER & HIP CALCULATIONS ---
        if (kp.length > 12) {
            try {
                const Rm = this.compute_rotation_matrix(p(8).sub(p(11)), p(12).sub(p(11)));
                const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(Rm);
                angles["R Shoulder (X-Axis Rotation)"] = rx.toFixed(1);
                angles["R Shoulder (Y-Axis Rotation)"] = ry.toFixed(1);
                angles["R Shoulder (Z-Axis Rotation)"] = rz.toFixed(1);
            } catch (e) { console.error("R Shoulder calc error", e); }
        }
        if (kp.length > 15) {
            try {
                const Rm = this.compute_rotation_matrix(p(8).sub(p(14)), p(15).sub(p(14)));
                const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(Rm);
                angles["L Shoulder (X-Axis Rotation)"] = rx.toFixed(1);
                angles["L Shoulder (Y-Axis Rotation)"] = (-ry).toFixed(1);
                angles["L Shoulder (Z-Axis Rotation)"] = (-rz).toFixed(1);
            } catch (e) { console.error("L Shoulder calc error", e); }
        }
        if (kp.length > 2) {
            try {
                const Rm = this.compute_rotation_matrix(p(0).sub(p(1)), p(2).sub(p(1)));
                const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(Rm);
                angles["R Hip (X-Axis Rotation)"] = rx.toFixed(1);
                angles["R Hip (Y-Axis Rotation)"] = ry.toFixed(1);
                angles["R Hip (Z-Axis Rotation)"] = rz.toFixed(1);
            } catch (e) { console.error("R Hip calc error", e); }
        }
        if (kp.length > 5) {
            try {
                const Rm = this.compute_rotation_matrix(p(0).sub(p(4)), p(5).sub(p(4)));
                const [rx, ry, rz] = this.rotation_matrix_to_euler_angles(Rm);
                angles["L Hip (X-Axis Rotation)"] = rx.toFixed(1);
                angles["L Hip (Y-Axis Rotation)"] = (-ry).toFixed(1);
                angles["L Hip (Z-Axis Rotation)"] = (-rz).toFixed(1);
            } catch (e) { console.error("L Hip calc error", e); }
        }
        return angles;
    },

    /**
     * Main processing function to compute all 23 kinematic angles for a single pose.
     * @param {Array<number[]>} keypoints - Array of 17 3D keypoints for one frame.
     * @returns {Object} An object containing all calculated angle values, keyed by name.
     */
    process_all_angles: function(keypoints) {
        if (!keypoints || keypoints.length < 17) {
             // Return all keys with 0.0 if not enough keypoints
            const all_angles = {};
            ANGLE_KEYS.forEach(key => {
                all_angles[key] = "0.0";
            });
            return all_angles;
        }
        
        const all_angles = {};
        
        // 1. Simple Bend Angles (Knees and Elbows)
        const bend_checks = [
            [1, 2, 3, "R_Knee"], [4, 5, 6, "L_Knee"],
            [11, 12, 13, "R_Elbow"], [14, 15, 16, "L_Elbow"]
        ];
        bend_checks.forEach(([A, B, C, name]) => {
            all_angles[`${name} (Bend)`] = this.calculate_3d_angle(keypoints[A], keypoints[B], keypoints[C]).toFixed(1);
        });

        // 2. Simple Vertical Angle (Torso)
        if (keypoints.length > 8) {
             all_angles["Torso-Neck (Vertical)"] = this.calculate_vertical_angle(keypoints[7], keypoints[8]).toFixed(1);
        }

        // 3. Complex 3D Anatomical Angles (Hips, Shoulders, Waist, Neck)
        Object.assign(all_angles, this.calculate_anatomical_angles(keypoints));
        
        // 4. Final check to ensure all angle keys exist in the output, defaulting to "0.0".
        ANGLE_KEYS.forEach(key => {
            if (!all_angles[key]) {
                all_angles[key] = "0.0";
            }
        });
        
        return all_angles;
    }
};