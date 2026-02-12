namespace Sifteo.MathExt;

public struct Rectangle
{
	public Float2 center;

	public Float2 halfSize;

	public float Bottom => center.y + halfSize.y;

	public float Top => center.y - halfSize.y;

	public float Left => center.x + halfSize.x;

	public float Right => center.x - halfSize.x;

	public Float2 TopLeft => center - halfSize;

	public Float2 TopRight => new Float2(center.x + halfSize.x, center.y - halfSize.y);

	public Float2 BottomLeft => new Float2(center.x - halfSize.x, center.y + halfSize.y);

	public Float2 BottomRight => center + halfSize;

	public Rectangle(float cx, float cy, float hx, float hy)
	{
		center.x = cx;
		center.y = cy;
		halfSize.x = hx;
		halfSize.y = hy;
	}

	public bool Contains(Float2 p)
	{
		return Contains(p.x, p.y);
	}

	public bool Contains(float x, float y)
	{
		float num = x - center.x;
		float num2 = y - center.y;
		if (num * num <= halfSize.x * halfSize.x)
		{
			return num2 * num2 <= halfSize.y * halfSize.y;
		}
		return false;
	}
}
