import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';

import { photoResize } from './presentation';

export class CameraPermissionError extends Error {}

function deleteFile(uri: string): void {
  const file = new File(uri);
  if (file.exists) file.delete();
}

/**
 * Opens the system camera and returns a reduced JPEG of the label in the app cache,
 * or null if the user cancelled. The caller deletes it after uploading
 * (see `withTemporaryPhoto`); the original capture is deleted here.
 */
export async function takeLabelPhoto(): Promise<string | null> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) throw new CameraPermissionError('Permite el acceso a la cámara en los ajustes del teléfono para fotografiar etiquetas.');
  const result = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.8, exif: false, allowsEditing: false });
  if (result.canceled || !result.assets[0]) return null;
  const capture = result.assets[0];
  const resize = photoResize(capture.width, capture.height);
  try {
    const context = ImageManipulator.manipulate(capture.uri);
    if (resize) context.resize(resize);
    const image = await context.renderAsync();
    const saved = await image.saveAsync({ compress: 0.7, format: SaveFormat.JPEG });
    return saved.uri;
  } finally {
    try { deleteFile(capture.uri); } catch { /* The OS clears the cache directory eventually. */ }
  }
}

export function deleteTemporaryPhoto(uri: string): void {
  deleteFile(uri);
}
