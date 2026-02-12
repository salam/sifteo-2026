using System;

namespace Sifteo.MathExt;

public class Mathf
{
	public const float Pi = (float)Math.PI;

	public const float Tau = (float)Math.PI * 2f;

	public const float Rad2Deg = 57.29578f;

	public const float Deg2Rad = (float)Math.PI / 180f;

	public const float E = (float)Math.E;

	public const float Epsilon = 1E-05f;

	public static Random Seed = new Random();

	public static float RandomValue => (float)Seed.NextDouble();

	public static float RandomRange(float u, float v)
	{
		return (float)((double)u + Seed.NextDouble() * (double)(v - u));
	}

	public static int DiceRoll(int d)
	{
		return Seed.Next() % d;
	}

	public static float Sqrt(float u)
	{
		return (float)Math.Sqrt(u);
	}

	public static float Abs(float u)
	{
		return Math.Abs(u);
	}

	public static float Max(float u, float v)
	{
		return Math.Max(u, v);
	}

	public static float Min(float u, float v)
	{
		return Math.Min(u, v);
	}

	public static float Clamp(float u, float min, float max)
	{
		return Min(Max(u, min), max);
	}

	public static int Clamp(int x, int min, int max)
	{
		if (x >= min)
		{
			if (x <= max)
			{
				return x;
			}
			return max;
		}
		return min;
	}

	public static float Clamp01(float u)
	{
		return Min(Max(u, 0f), 1f);
	}

	public static int Mod(int a, int b)
	{
		if (a >= 0)
		{
			return a % b;
		}
		return b + a % b;
	}

	public static float Mod(float a, float b)
	{
		if (!(a < 0f))
		{
			return a % b;
		}
		return b + a % b;
	}

	public static float Wrap01(float u)
	{
		u %= 1f;
		if (!(u < 0f))
		{
			return u;
		}
		return u + 1f;
	}

	public static float Sin(float u)
	{
		return (float)Math.Sin(u);
	}

	public static float Cos(float u)
	{
		return (float)Math.Cos(u);
	}

	public static float Tan(float u)
	{
		return (float)Math.Tan(u);
	}

	public static float Asin(float u)
	{
		return (float)Math.Asin(u);
	}

	public static float Acos(float u)
	{
		return (float)Math.Acos(u);
	}

	public static float Atan(float u)
	{
		return (float)Math.Atan(u);
	}

	public static float Atan2(float dy, float dx)
	{
		return (float)Math.Atan2(dy, dx);
	}

	public static float Pow(float u, float v)
	{
		return (float)Math.Pow(u, v);
	}

	public static float Exp(float u)
	{
		return (float)Math.Exp(u);
	}

	public static float NaturalLog(float u)
	{
		return (float)Math.Log(u);
	}

	public static float Log10(float u)
	{
		return (float)Math.Log10(u);
	}

	public static float Sign(float u)
	{
		return Math.Sign(u);
	}

	public static float Ceil(float u)
	{
		return (float)Math.Ceiling(u);
	}

	public static float Round(float u)
	{
		return (float)Math.Round(u);
	}

	public static float Floor(float u)
	{
		return (float)Math.Floor(u);
	}

	public static int FloorToInt(float u)
	{
		return (int)Math.Floor(u);
	}

	public static int TruncateToInt(float u)
	{
		return (int)Math.Truncate(u);
	}

	public static float Truncate(float u)
	{
		return (float)Math.Truncate(u);
	}

	public static float Lerp(float a, float b, float t)
	{
		return a + t * (b - a);
	}

	public static float InverseLerp(float a, float b, float u)
	{
		return (u - a) / (b - a);
	}

	public static float DeltaRadians(float lhs, float rhs)
	{
		float num = (lhs - rhs) % ((float)Math.PI * 2f);
		if (num < -(float)Math.PI)
		{
			return num + (float)Math.PI * 2f;
		}
		if (num > (float)Math.PI)
		{
			return num - (float)Math.PI * 2f;
		}
		return num;
	}

	public static float Bezier(float a, float b, float c, float u)
	{
		return (1f - u) * (1f - u) * a + 2f * (1f - u) * u * b + u * u * c;
	}

	public static Float2 Bezier(Float2 a, Float2 b, Float2 c, float u)
	{
		return (1f - u) * (1f - u) * a + 2f * (1f - u) * u * b + u * u * c;
	}

	public static float BezierDeriv(float a, float b, float c, float u)
	{
		return 2f * (1f - u) * (b - a) + 2f * u * (c - b);
	}

	public static Float2 BezierDeriv(Float2 a, Float2 b, Float2 c, float u)
	{
		return 2f * (1f - u) * (b - a) + 2f * u * (c - b);
	}

	public static float Bezier(float a, float b, float c, float d, float u)
	{
		return (1f - u) * (1f - u) * (1f - u) * a + 3f * (1f - u) * (1f - u) * u * b + 3f * (1f - u) * u * u * c + u * u * u * d;
	}

	public static Float2 Bezier(Float2 a, Float2 b, Float2 c, Float2 d, float u)
	{
		return (1f - u) * (1f - u) * (1f - u) * a + 3f * (1f - u) * (1f - u) * u * b + 3f * (1f - u) * u * u * c + u * u * u * d;
	}
}
