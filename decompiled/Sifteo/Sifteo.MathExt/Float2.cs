namespace Sifteo.MathExt;

public struct Float2
{
	public static readonly Float2 Zero = new Float2(0f, 0f);

	public static readonly Float2 Identity = new Float2(1f, 0f);

	public static readonly Float2 One = new Float2(1f, 1f);

	public static readonly Float2 Left = new Float2(-1f, 0f);

	public static readonly Float2 Right = new Float2(1f, 0f);

	public static readonly Float2 Up = new Float2(0f, -1f);

	public static readonly Float2 Down = new Float2(0f, 1f);

	private static readonly Float2[] kSideToFloat2 = new Float2[5]
	{
		new Float2(0f, -1f),
		new Float2(-1f, 0f),
		new Float2(0f, 1f),
		new Float2(1f, 0f),
		new Float2(0f, 0f)
	};

	public float x;

	public float y;

	public float Norm => x * x + y * y;

	public float Magnitude => Mathf.Sqrt(x * x + y * y);

	public float Radians => Mathf.Atan2(y, x);

	public Float2 Reflection => new Float2(y, x);

	public Float2 Anticlockwise => new Float2(y, 0f - x);

	public Float2 Clockwise => new Float2(0f - y, x);

	public Float2 Conjugate => new Float2(x, 0f - y);

	public Float2(float x, float y)
	{
		this.x = x;
		this.y = y;
	}

	public static Float2 Polar(float radians, float radius = 1f)
	{
		return new Float2(radius * Mathf.Cos(radians), radius * Mathf.Sin(radians));
	}

	public static Float2 Side(Cube.Side side)
	{
		return kSideToFloat2[(int)side];
	}

	public static bool Approx(Float2 u, Float2 v, float ep = 0.001f)
	{
		return (u - v).Norm < ep * ep;
	}

	public override string ToString()
	{
		return $"({x}, {y})";
	}

	public static Float2 operator -(Float2 v)
	{
		return new Float2(0f - v.x, 0f - v.y);
	}

	public static Float2 operator +(Float2 u, Float2 v)
	{
		return new Float2(u.x + v.x, u.y + v.y);
	}

	public static Float2 operator -(Float2 u, Float2 v)
	{
		return new Float2(u.x - v.x, u.y - v.y);
	}

	public static Float2 operator *(float scalar, Float2 u)
	{
		return new Float2(scalar * u.x, scalar * u.y);
	}

	public static Float2 operator *(Float2 u, float scalar)
	{
		return new Float2(scalar * u.x, scalar * u.y);
	}

	public static Float2 operator /(Float2 u, float scalar)
	{
		scalar = 1f / scalar;
		return new Float2(u.x * scalar, u.y * scalar);
	}

	public static Float2 operator *(Float2 l, Float2 r)
	{
		return new Float2(l.x * r.x - l.y * r.y, l.x * r.y + l.y * r.x);
	}

	public static Float2 operator /(Float2 l, Float2 r)
	{
		float num = 1f / r.Norm;
		return new Float2(Dot(l, r) * num, Cross(l, r) * num);
	}

	public void Normalize()
	{
		float magnitude = Magnitude;
		if (magnitude > 1E-05f)
		{
			magnitude = 1f / magnitude;
			x *= magnitude;
			y *= magnitude;
		}
	}

	public static float Dot(Float2 u, Float2 v)
	{
		return u.x * v.x + u.y * v.y;
	}

	public static float Cross(Float2 u, Float2 v)
	{
		return v.x * u.y - u.x * v.y;
	}

	public static float AngleBetween(Float2 u, Float2 v)
	{
		return Mathf.Acos(Dot(u, v) / (u.Magnitude * v.Magnitude));
	}

	public static Float2 Lerp(Float2 u, Float2 v, float t)
	{
		return new Float2(u.x + t * (v.x - u.x), u.y + t * (v.y - u.y));
	}

	public static Float2 Slerp(Float2 u, Float2 v, float t)
	{
		float num = AngleBetween(u, v);
		float num2 = 1f / Mathf.Sin(num);
		float num3 = Mathf.Sin((1f - t) * num) * num2;
		float num4 = Mathf.Sin(t * num) * num2;
		return new Float2(num3 * u.x + num4 * v.x, num3 * u.y + num4 * v.y);
	}
}
