using Sifteo.MathExt;

namespace Sifteo.Util;

public class Sprite
{
	public enum PivotMode
	{
		Center,
		Corner
	}

	public PivotMode pivotMode;

	public SpriteData data;

	public bool visible = true;

	public Int2 position = Int2.Zero;

	public int scale = 1;

	public int rotation;

	private AABB mDirtyRect = new AABB(0, 0, 0, 0);

	public bool IsVisible
	{
		get
		{
			if (data != null)
			{
				return visible;
			}
			return false;
		}
	}

	public AABB DirtyRect => mDirtyRect;

	public bool HasDirtyRect
	{
		get
		{
			if (mDirtyRect.size.x != 0)
			{
				return mDirtyRect.size.y != 0;
			}
			return false;
		}
	}

	public AABB AABB => new AABB(LeftTop, size);

	public Cube.Side Orientation
	{
		get
		{
			return (Cube.Side)(rotation % 4);
		}
		set
		{
			rotation = (int)value;
		}
	}

	public Int2 LeftTop
	{
		get
		{
			Int2 result = position;
			switch (rotation % 4)
			{
			case 1:
				result.x -= scale * data.pivot.y;
				result.y += scale * (data.pivot.x - data.size.x + 1);
				if (pivotMode == PivotMode.Corner)
				{
					result.y -= scale;
				}
				break;
			case 2:
				result += scale * (data.pivot - data.size + Int2.One);
				if (pivotMode == PivotMode.Corner)
				{
					result.x -= scale;
					result.y -= scale;
				}
				break;
			case 3:
				result.x += scale * (data.pivot.y - data.size.y + 1);
				result.y -= scale * data.pivot.x;
				if (pivotMode == PivotMode.Corner)
				{
					result.x -= scale;
				}
				break;
			default:
				result -= scale * data.pivot;
				break;
			}
			return result;
		}
	}

	public Int2 size
	{
		get
		{
			Int2 result = scale * data.size;
			if (rotation % 2 != 1)
			{
				return result;
			}
			return result.Reflection;
		}
	}

	public Sprite(SpriteData data = null)
	{
		this.data = data;
	}

	public void ClearDirtyRect()
	{
		mDirtyRect = new AABB(0, 0, 0, 0);
	}

	public void Paint(Cube c)
	{
		if (!IsVisible)
		{
			mDirtyRect = new AABB(0, 0, 0, 0);
			return;
		}
		Int2 leftTop = LeftTop;
		c.Image(data.imageName, leftTop.x, leftTop.y, data.source.x, data.source.y, data.size.x, data.size.y, scale, rotation);
		mDirtyRect.position = leftTop;
		mDirtyRect.size = data.size;
	}

	public void PaintMasked(Cube c, AABB worldBounds)
	{
		if (!IsVisible)
		{
			mDirtyRect = new AABB(0, 0, 0, 0);
			return;
		}
		AABB aABB = AABB;
		if (aABB.Intersection(worldBounds, out var result))
		{
			Int2 source = data.source;
			switch (rotation % 4)
			{
			case 1:
			{
				Int2 int2 = (result.BottomLeft - aABB.BottomLeft) / scale;
				source.x -= int2.y;
				source.y += int2.x;
				break;
			}
			case 2:
				source -= (result.BottomRight - aABB.BottomRight) / scale;
				break;
			case 3:
			{
				Int2 @int = (result.TopRight - aABB.TopRight) / scale;
				source.x += @int.y;
				source.y -= @int.x;
				break;
			}
			default:
				source += (result.TopLeft - aABB.TopLeft) / scale;
				break;
			}
			int num = (result.size.x + scale - 1) / scale;
			int num2 = (result.size.y + scale - 1) / scale;
			if (rotation % 2 == 1)
			{
				int num3 = num;
				num = num2;
				num2 = num3;
			}
			c.Image(data.imageName, result.position.x, result.position.y, source.x, source.y, num, num2, scale, rotation);
			mDirtyRect.position = result.position;
			mDirtyRect.size.x = num;
			mDirtyRect.size.y = num2;
		}
		else
		{
			mDirtyRect = new AABB(0, 0, 0, 0);
		}
	}
}
