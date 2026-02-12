using System;

namespace Sifteo.MathExt;

public struct AABB
{
	public Int2 position;

	public Int2 size;

	public Int2 TopLeft
	{
		get
		{
			return position;
		}
		set
		{
			Top = value.y;
			Left = value.x;
		}
	}

	public Int2 TopRight
	{
		get
		{
			return new Int2(position.x + size.x, position.y);
		}
		set
		{
			Top = value.y;
			Right = value.x;
		}
	}

	public Int2 BottomLeft
	{
		get
		{
			return new Int2(position.x, position.y + size.y);
		}
		set
		{
			Bottom = value.y;
			Left = value.x;
		}
	}

	public Int2 BottomRight
	{
		get
		{
			return position + size;
		}
		set
		{
			Bottom = value.y;
			Right = value.x;
		}
	}

	public int Left
	{
		get
		{
			return position.x;
		}
		set
		{
			size.x += position.x - value;
			position.x = value;
		}
	}

	public int Right
	{
		get
		{
			return position.x + size.x;
		}
		set
		{
			size.x = value - position.x;
		}
	}

	public int Top
	{
		get
		{
			return position.y;
		}
		set
		{
			size.y += position.y - value;
			position.y = value;
		}
	}

	public int Bottom
	{
		get
		{
			return position.y + size.y;
		}
		set
		{
			size.y = value - position.y;
		}
	}

	public AABB(int x, int y, int sx, int sy)
	{
		position.x = x;
		position.y = y;
		size.x = sx;
		size.y = sy;
	}

	public AABB(Int2 position, Int2 size)
	{
		this.position = position;
		this.size = size;
	}

	public static AABB Union(AABB u, AABB v)
	{
		int num = Math.Min(u.position.x, v.position.x);
		int num2 = Math.Min(u.position.y, v.position.y);
		int num3 = Math.Max(u.position.x + u.size.x, v.position.x + v.size.x);
		int num4 = Math.Max(u.position.y + u.size.y, v.position.y + v.size.y);
		return new AABB(num, num2, num3 - num, num4 - num2);
	}

	public bool Overlaps(AABB u)
	{
		AABB aABB = Union(u, this);
		if (aABB.size.x < u.size.x + size.x)
		{
			return aABB.size.y < u.size.y + size.y;
		}
		return false;
	}

	public override string ToString()
	{
		return $"({position},{size})";
	}

	public bool Intersection(AABB u, out AABB result)
	{
		int num = Math.Max(Left, u.Left);
		int num2 = Math.Min(Right, u.Right);
		if (num >= num2)
		{
			result.position.x = 0;
			result.position.y = 0;
			result.size.x = 0;
			result.size.y = 0;
			return false;
		}
		int num3 = Math.Max(Top, u.Top);
		int num4 = Math.Min(Bottom, u.Bottom);
		if (num3 >= num4)
		{
			result.position.x = 0;
			result.position.y = 0;
			result.size.x = 0;
			result.size.y = 0;
			return false;
		}
		result.position.x = num;
		result.position.y = num3;
		result.size.x = num2 - num;
		result.size.y = num4 - num3;
		return true;
	}

	public static bool AreTouching(AABB u, AABB v)
	{
		AABB aABB = Union(u, v);
		return (aABB.size.x == u.size.x + v.size.x) ^ (aABB.size.y == u.size.y + v.size.y);
	}

	public bool ContainsInclusive(int x, int y)
	{
		if (x >= position.x && y >= position.y && x <= position.x + size.x)
		{
			return y <= position.y + size.y;
		}
		return false;
	}

	public bool ContainsInclusive(Int2 u)
	{
		return ContainsInclusive(u.x, u.y);
	}

	public bool ContainsExclusive(int x, int y)
	{
		if (x >= position.x && y >= position.y && x < position.x + size.x)
		{
			return y < position.y + size.y;
		}
		return false;
	}

	public bool ContainsExclusive(Int2 u)
	{
		return ContainsExclusive(u.x, u.y);
	}
}
