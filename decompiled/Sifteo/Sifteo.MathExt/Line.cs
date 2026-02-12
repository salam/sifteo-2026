namespace Sifteo.MathExt;

public struct Line
{
	public Float2 p0;

	public Float2 p1;

	public Float2 Delta => p1 - p0;

	public Line(float x0, float y0, float x1, float y1)
	{
		p0.x = x0;
		p0.y = y0;
		p1.x = x1;
		p1.y = y1;
	}

	public Line(Float2 p0, Float2 p1)
	{
		this.p0 = p0;
		this.p1 = p1;
	}

	public Float2 ValueAt(float u)
	{
		return p0 + u * (p1 - p0);
	}

	public Float2 DerivAt(float u)
	{
		return p1 - p0;
	}

	public void Offset(Float2 delta)
	{
		p0 += delta;
		p1 += delta;
	}

	public static bool Intersection(Line U, Line V, out float u, float slop = 0.0001f)
	{
		float num = (V.p1.y - V.p0.y) * (U.p1.x - U.p0.x) - (V.p1.x - V.p0.x) * (U.p1.y - U.p0.y);
		if (num > 0f - slop && num < slop)
		{
			u = 0f;
			return false;
		}
		num = 1f / num;
		u = ((V.p1.x - V.p0.x) * (U.p0.y - V.p0.y) - (V.p1.y - V.p0.y) * (U.p0.x - V.p0.x)) * num;
		return true;
	}

	public static bool Intersection(Line U, Line V, out float u, out float v, float slop = 0.0001f)
	{
		float num = (V.p1.y - V.p0.y) * (U.p1.x - U.p0.x) - (V.p1.x - V.p0.x) * (U.p1.y - U.p0.y);
		if (num > 0f - slop && num < slop)
		{
			u = 0f;
			v = 0f;
			return false;
		}
		num = 1f / num;
		u = ((V.p1.x - V.p0.x) * (U.p0.y - V.p0.y) - (V.p1.y - V.p0.y) * (U.p0.x - V.p0.x)) * num;
		v = ((U.p1.x - U.p0.x) * (U.p0.y - V.p0.y) - (U.p1.y - U.p0.y) * (U.p0.x - V.p0.x)) * num;
		return true;
	}
}
