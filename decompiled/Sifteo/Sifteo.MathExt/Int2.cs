namespace Sifteo.MathExt;

public struct Int2
{
	public static Int2 Zero = new Int2(0, 0);

	public static Int2 One = new Int2(1, 1);

	public static Int2 Left = new Int2(-1, 0);

	public static Int2 Right = new Int2(1, 0);

	public static Int2 Up = new Int2(0, -1);

	public static Int2 Down = new Int2(0, 1);

	public int x;

	public int y;

	private static readonly Int2[] kSideToPair = new Int2[5]
	{
		new Int2(0, -1),
		new Int2(-1, 0),
		new Int2(0, 1),
		new Int2(1, 0),
		new Int2(0, 0)
	};

	public int Norm => x * x + y * y;

	public Int2 Reflection => new Int2(y, x);

	public Int2 Anticlockwise => new Int2(y, -x);

	public Int2 Clockwise => new Int2(-y, x);

	public Int2 Conjugate => new Int2(x, -y);

	public Int2(int x, int y)
	{
		this.x = x;
		this.y = y;
	}

	public static Int2 Side(Cube.Side side)
	{
		return kSideToPair[(int)side];
	}

	public override string ToString()
	{
		return $"({x}, {y})";
	}

	public static Int2 operator -(Int2 v)
	{
		return new Int2(-v.x, -v.y);
	}

	public static Int2 operator +(Int2 u, Int2 v)
	{
		return new Int2(u.x + v.x, u.y + v.y);
	}

	public static Int2 operator -(Int2 u, Int2 v)
	{
		return new Int2(u.x - v.x, u.y - v.y);
	}

	public static Int2 operator *(Int2 l, Int2 r)
	{
		return new Int2(l.x * r.x - l.y * r.y, l.x * r.y + l.y * r.x);
	}

	public static Int2 operator /(Int2 l, Int2 r)
	{
		return new Int2(Dot(l, r), Cross(l, r)) / r.Norm;
	}

	public static Int2 operator *(int scalar, Int2 u)
	{
		return new Int2(scalar * u.x, scalar * u.y);
	}

	public static Int2 operator *(Int2 u, int scalar)
	{
		return new Int2(scalar * u.x, scalar * u.y);
	}

	public static Int2 operator /(Int2 u, int scalar)
	{
		return new Int2(u.x / scalar, u.y / scalar);
	}

	public static int Dot(Int2 u, Int2 v)
	{
		return u.x * v.x + u.y * v.y;
	}

	public static int Cross(Int2 u, Int2 v)
	{
		return v.x * u.y - u.x * v.y;
	}
}
