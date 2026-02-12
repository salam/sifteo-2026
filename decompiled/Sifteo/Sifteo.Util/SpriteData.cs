using Sifteo.MathExt;

namespace Sifteo.Util;

public class SpriteData
{
	public string imageName;

	public Int2 source;

	public Int2 size;

	public Int2 pivot;

	public SpriteData(string imageName, int sourceX, int sourceY, int width, int height, int pivotX = 0, int pivotY = 0)
	{
		this.imageName = imageName;
		source.x = sourceX;
		source.y = sourceY;
		size.x = width;
		size.y = height;
		pivot.x = pivotX;
		pivot.y = pivotY;
	}
}
