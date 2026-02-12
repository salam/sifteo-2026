namespace Sifteo.MathExt;

public struct Transform
{
	public Float2 t;

	public Float2 q;

	public static readonly Transform Identity = new Transform(Float2.Zero, Float2.Identity);

	public Transform Inverse
	{
		get
		{
			Float2 @float = Float2.Identity / q;
			return new Transform(-t * @float, @float);
		}
	}

	public Transform(Float2 t, Float2 q)
	{
		this.t = t;
		this.q = q;
	}

	public Float2 TransformPoint(Float2 p)
	{
		return p * q + t;
	}

	public Float2 InverseTransformPoint(Float2 p)
	{
		return (p - t) / q;
	}

	public Float2 TransformDirection(Float2 v)
	{
		return v * q;
	}

	public Float2 InverseTransformDirection(Float2 v)
	{
		return v / q;
	}

	public static Transform operator *(Transform u, Transform v)
	{
		return new Transform(v.q * u.t + v.t, u.q * v.q);
	}
}
