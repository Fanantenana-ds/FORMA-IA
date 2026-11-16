const readBlobAsDataUrl = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('Image illisible.'));
    reader.onerror = () => reject(new Error('Impossible de lire cette image.'));
    reader.readAsDataURL(blob);
  });

const decodeImage = (source: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Le fichier choisi ne contient pas une image valide.'));
    image.src = source;
  });

export const prepareProfileAvatar = async (file: File): Promise<Blob> => {
  if (!file.type.startsWith('image/')) throw new Error('Choisissez un fichier image.');
  if (file.size > 8 * 1024 * 1024) throw new Error('La photo doit peser moins de 8 Mo.');

  const image = await decodeImage(await readBlobAsDataUrl(file));
  const scale = Math.min(1, 512 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Le navigateur ne peut pas traiter cette image.');

  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const compressed = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Impossible de compresser cette image.')), 'image/jpeg', 0.84);
  });
  if (compressed.size > 1024 * 1024) throw new Error('La photo compressée dépasse 1 Mo. Choisissez une image plus simple.');
  return compressed;
};

export const profileAvatarDataUrl = readBlobAsDataUrl;
