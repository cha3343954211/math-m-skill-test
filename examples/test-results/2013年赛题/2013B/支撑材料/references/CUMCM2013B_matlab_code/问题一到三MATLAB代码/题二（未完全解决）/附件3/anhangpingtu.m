function [I] = anhangpingtu(cell,xu)


for i = 1:length(xu)      %length(xu)
    I(:,72*(i-1)+1:72*i)=cell{1,xu(i)};       %½«Í¼¸´Ô­
end



end

