/**
 * @file constants.js
 * @description Provides constants and helpers for the UI-PRMD Vicon dataset.
 * The joint order and names are derived from Table 2 of the dataset's paper.
 */

// An array of the 39 joint names in the order they appear in the Vicon data file.
const UIPRMD_VICON_JOINT_ORDER = [
    'Head', 'Left head', 'Right head', 'Left neck', 'Right neck', 'Left clavicle', 'Right clavicle', 'Thorax',
    'Left thorax', 'Right thorax', 'Pelvis', 'Left pelvis', 'Right pelvis', 'Left hip', 'Right hip',
    'Left femur', 'Right femur', 'Left knee', 'Right knee', 'Left tibia', 'Right tibia', 'Left ankle', 'Right ankle',
    'Left foot', 'Right foot', 'Left toe', 'Right toe', 'Left shoulder', 'Right shoulder', 'Left elbow', 'Right elbow',
    'Left radius', 'Right radius', 'Left wrist', 'Right wrist', 'Left upperhand', 'Right upperhand',
    'Left hand', 'Right hand'
];

// Generates a flat list of all 117 angle keys (e.g., 'Head_Y', 'Head_X', 'Head_Z')
export const UIPRMD_ANGLE_KEYS = UIPRMD_VICON_JOINT_ORDER.flatMap(
    joint => [`${joint}_Y`, `${joint}_X`, `${joint}_Z`]
);

/**
 * Groups the 39 Vicon joints into logical body parts for visualization.
 * @returns {Object} An object where keys are group names and values are arrays of joint names.
 */
export const getGroupedJoints = () => {
    return {
        'Head & Torso': ['Head', 'Left head', 'Right head', 'Left neck', 'Right neck', 'Left clavicle', 'Right clavicle', 'Thorax', 'Left thorax', 'Right thorax', 'Pelvis', 'Left pelvis', 'Right pelvis'],
        'Right Arm': ['Right shoulder', 'Right elbow', 'Right radius', 'Right wrist', 'Right upperhand', 'Right hand'],
        'Left Arm': ['Left shoulder', 'Left elbow', 'Left radius', 'Left wrist', 'Left upperhand', 'Left hand'],
        'Right Leg': ['Right hip', 'Right femur', 'Right knee', 'Right tibia', 'Right ankle', 'Right foot', 'Right toe'],
        'Left Leg': ['Left hip', 'Left femur', 'Left knee', 'Left tibia', 'Left ankle', 'Left foot', 'Left toe']
    };
};